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
        self.assertEqual(set(doc), {"scanner", "mode", "target", "ioc_version", "verdict", "counts", "findings"})
        self.assertEqual(doc["scanner"], "shai-hulud")
        self.assertEqual(doc["counts"]["CRITICAL"], 1)
        self.assertIn("AFFECTED", self.f.to_text(doc))


if __name__ == "__main__":
    unittest.main()
