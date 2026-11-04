#!/usr/bin/env python3
"""Security tests for job-security-scan itself: config injection, unsafe repo names, XML entities,
URL schemes, secret leakage into raw output and reports, issue-body mentions, and the opt-in,
sandboxed Docker image probe.

Run: python3 -I scripts/test-hardening.py [TestClass ...] [-v]
No network, no scanner binaries (docker is stubbed on PATH). Stdlib only; Python 3.8+.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SKILL_DIR / "scripts" / "lib"))
sys.path.insert(0, str(SKILL_DIR / "scripts"))

PARSE_CONFIG = SKILL_DIR / "scripts" / "parse-config.py"
RUN_SCAN = SKILL_DIR / "scripts" / "run-scan.sh"
FETCH_IOCS = SKILL_DIR / "scripts" / "fetch-iocs.py"
PROBE = SKILL_DIR / "scripts" / "probe-runtime.py"
FIX = SKILL_DIR / "tests" / "fixtures"
SECRET = "AKIA" + "HARDENINGTEST0000"


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


def load_script(name):
    import importlib.util
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), str(SKILL_DIR / "scripts" / name))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class ConfigInjectionTests(TempDirCase):
    def parse(self, body):
        cfg = self.put("repository.md", body)
        return subprocess.run([sys.executable, "-I", str(PARSE_CONFIG), str(cfg)], stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, universal_newlines=True, cwd=str(self.tmp))

    def test_values_cannot_run_commands_when_sourced(self):
        evil = 'x"; touch %s/PWNED; echo "' % self.tmp
        r = self.parse('---\nteam: %s\norg: $(touch %s/PWNED2)\nci-branches:\n  - "a`touch %s/PWNED3`"\n'
                       'repos:\n  - name: svc\n    active: true\n---\n' % (evil, self.tmp, self.tmp))
        self.assertEqual(r.returncode, 0, r.stderr)
        sh = subprocess.run(["bash", "-c", 'eval "$1"; printf "%s" "$TEAM"', "_", r.stdout],
                            stdout=subprocess.PIPE, universal_newlines=True)
        self.assertEqual(sh.stdout, evil.strip().strip('"').strip())  # the YAML reader trims outer quotes
        for f in ("PWNED", "PWNED2", "PWNED3"):
            self.assertFalse((self.tmp / f).exists(), f)

    def test_unsafe_repo_names_rejected(self):
        for name in ("../escape", "a/b", "x');import os;os.system('id", "-rf", ".hidden", "name with space"):
            r = self.parse("---\nteam: t\nrepos:\n  - name: %s\n    active: true\n---\n" % name)
            self.assertNotEqual(r.returncode, 0, name)
            self.assertIn("repo name", r.stderr)

    def test_normal_repo_names_accepted(self):
        r = self.parse("---\nteam: t\nrepos:\n  - name: om-ddm_backend.v2\n    active: true\n---\n")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("om-ddm_backend.v2", r.stdout)


class ShellCodeInjectionTests(unittest.TestCase):
    def test_no_shell_variables_inside_python_code(self):
        text = RUN_SCAN.read_text()
        for marker in ("open('$", 'open("$', "load_json('$"):
            self.assertNotIn(marker, text)

    def test_installer_never_pipes_downloads_into_a_shell(self):
        text = (SKILL_DIR / "scripts" / "install-tools.sh").read_text()
        self.assertNotRegex(text, r"curl[^\n]*\|\s*(sudo\s+)?(ba)?sh")
        evals = [l.strip() for l in text.splitlines() if l.strip().startswith("eval ")]
        self.assertEqual(evals, ['eval "$CONFIG_SH"'])   # only the shell-quoted config, never a download
        self.assertNotIn("releases/latest", text)
        self.assertNotIn("/main/", text)
        self.assertIn("sha256", text)


@unittest.skipUnless(shutil.which("bash") and sys.platform.startswith("linux"), "bash on Linux required")
class InstallerVerificationTests(TempDirCase):
    """install-tools.sh against a stub curl serving local release files: a good checksum installs,
    a tampered binary is refused and nothing is installed."""

    def release(self, tool, version, asset, content, sums_name, tamper=False):
        import hashlib
        import tarfile
        rel = self.tmp / "releases"
        rel.mkdir(exist_ok=True)
        src = self.tmp / "src" / tool
        src.parent.mkdir(exist_ok=True)
        src.write_text("#!/bin/sh\necho %s %s\n" % (tool, version))
        with tarfile.open(str(rel / asset), "w:gz") as tf:
            tf.add(str(src), arcname=tool)
        digest = hashlib.sha256((rel / asset).read_bytes()).hexdigest()
        if tamper:
            with tarfile.open(str(rel / asset), "w:gz") as tf:   # swapped after the sums were published
                src.write_text("#!/bin/sh\necho EVIL\n")
                tf.add(str(src), arcname=tool)
        (rel / sums_name).write_text("%s  %s\n%s  other-asset.tar.gz\n" % (digest, asset, "0" * 64))

    def test_good_checksum_installs_and_tampered_download_is_refused(self):
        self.release("trivy", "0.69.3", "trivy_0.69.3_Linux-64bit.tar.gz", "", "trivy_0.69.3_checksums.txt")
        self.release("gitleaks", "8.30.1", "gitleaks_8.30.1_linux_x64.tar.gz", "", "gitleaks_8.30.1_checksums.txt",
                     tamper=True)
        bin_dir = self.tmp / "bin"
        bin_dir.mkdir()
        curl = bin_dir / "curl"   # serves https://github.com/.../<asset> from ./releases/<asset>
        curl.write_text('#!/usr/bin/env bash\nout=""; url=""\nwhile [ $# -gt 0 ]; do case "$1" in -o) out="$2"; shift 2;; '
                        '--proto|--retry) shift 2;; -*) shift;; *) url="$1"; shift;; esac; done\n'
                        'f="%s/releases/${url##*/}"; [ -f "$f" ] || exit 22\n'
                        'if [ -n "$out" ]; then cp "$f" "$out"; else cat "$f"; fi\n' % self.tmp)
        curl.chmod(0o755)
        dest = self.tmp / "dest"
        cfg = self.put("repository.md", "---\nteam: t\norg: o\nrepos:\n  - name: svc\n    active: true\n---\n")
        path = os.pathsep.join([str(bin_dir)] + [p for p in os.environ["PATH"].split(os.pathsep)
                                                 if not any((Path(p) / t).exists() for t in
                                                            ("trivy", "gitleaks", "trufflehog", "osv-scanner"))])
        if (Path("/bin") / "uname").exists() and "x86_64" not in subprocess.run(
                ["uname", "-m"], stdout=subprocess.PIPE, universal_newlines=True).stdout:
            self.skipTest("fixture assets are x86_64")
        r = subprocess.run(["bash", str(SKILL_DIR / "scripts" / "install-tools.sh"), "--config", str(cfg)],
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True,
                           env=dict(os.environ, PATH=path, INSTALL_DIR=str(dest)))
        self.assertTrue((dest / "trivy").is_file(), r.stdout)
        self.assertTrue(os.access(str(dest / "trivy"), os.X_OK))
        self.assertFalse((dest / "gitleaks").exists(), r.stdout)
        self.assertIn("checksum mismatch for gitleaks_8.30.1_linux_x64.tar.gz", r.stdout)
        self.assertIn("Failed tools", r.stdout)


class XmlTests(unittest.TestCase):
    def test_entity_declarations_refused(self):
        import adapters
        bomb = (b'<?xml version="1.0"?><!DOCTYPE r [<!ENTITY a "aaaaaaaaaa"><!ENTITY b "&a;&a;&a;&a;">]>'
                b'<rss><channel><item><title>&b; CVE-2026-1</title></item></channel></rss>')
        self.assertIsNone(adapters.feed_leads(bomb, "x"))

    def test_plain_feed_still_parsed(self):
        import adapters
        feed = (b'<?xml version="1.0"?><rss><channel><item><title>Fix for CVE-2026-1234</title>'
                b'<link>https://e.invalid/a</link></item></channel></rss>')
        leads = adapters.feed_leads(feed, "x")
        self.assertTrue(leads)


class FetchSchemeTests(TempDirCase):
    def fetch(self, url):
        src = self.put("sources.json", json.dumps({"sources": [
            {"id": "s", "wave": "sh-2.0", "ecosystem": "npm", "format": "csv-name-versions", "url": url}]}))
        return subprocess.run([sys.executable, "-I", str(FETCH_IOCS), "--out", str(self.tmp / "o"), "--sources", str(src)],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)

    def test_insecure_schemes_refused(self):
        for url in ("http://raw.githubusercontent.com/x.csv", "ftp://e.invalid/x.csv", "gopher://e.invalid/x"):
            r = self.fetch(url)
            self.assertEqual(r.returncode, 3, url)
            self.assertIn("refused", r.stderr, url)

    def test_https_host_must_be_allowlisted(self):
        r = self.fetch("https://evil.example/x.csv")
        self.assertEqual(r.returncode, 3)
        self.assertIn("not allowlisted", r.stderr)

    def test_local_file_still_allowed(self):
        p = self.put("l.csv", "package_name,package_version\nlocal-evil,1.0.0\n")
        self.assertEqual(self.fetch(p.as_uri()).returncode, 0)


class SecretLeakTests(TempDirCase):
    def test_trufflehog_raw_values_stripped(self):
        import sanitize
        out = self.put("trufflehog.json", "\n".join(json.dumps(d) for d in [
            {"DetectorName": "AWS", "Verified": True, "Raw": SECRET, "RawV2": SECRET + ":x", "Redacted": "AKIA****",
             "SourceMetadata": {"Data": {"Git": {"file": ".env", "line": 3}}}},
            {"DetectorName": "Github", "Verified": False, "Raw": "ghp_" + "x" * 36}]) + "\n")
        self.assertEqual(sanitize.strip_trufflehog(str(out)), 2)
        text = out.read_text()
        self.assertNotIn(SECRET, text)
        self.assertNotIn("ghp_", text)
        rows = [json.loads(l) for l in text.splitlines()]
        self.assertEqual(rows[0]["SourceMetadata"]["Data"]["Git"]["line"], 3)
        self.assertEqual(rows[0]["Redacted"], "AKIA****")
        self.assertTrue(rows[0]["Verified"])

    def test_verified_trufflehog_secret_fails_the_scan(self):
        if not shutil.which("bash"):
            self.skipTest("bash required")
        bin_dir = self.tmp / "bin"
        bin_dir.mkdir()
        th = bin_dir / "trufflehog"
        th.write_text('#!/usr/bin/env bash\necho \'{"DetectorName":"AWS","Verified":true,"Raw":"%s",'
                      '"SourceMetadata":{"Data":{"Git":{"file":".env","line":3}}}}\'\n' % SECRET)
        th.chmod(0o755)
        cfg = self.put("repository.md", '---\nteam: t\norg: o\nmonorepo-root: "%s"\nrepos:\n'
                       '  - name: clean\n    active: true\n---\n' % (FIX / "shai-hulud"))
        (self.tmp / "ws").mkdir()
        env = dict(os.environ, PATH=str(bin_dir) + os.pathsep + os.environ["PATH"],
                   JOB_SECURITY_SCAN_CACHE=str(self.tmp / "c"), SECURITY_RUN_ROOT=str(self.tmp / "ws"))
        r = subprocess.run(["bash", str(RUN_SCAN), "--config", str(cfg), "--scanner", "trufflehog"],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True,
                           cwd=str(self.tmp / "ws"), env=env)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("1 VERIFIED ACTIVE", r.stdout)
        run = sorted((self.tmp / "ws").glob("security-run-*"))[-1]
        for f in run.rglob("*"):
            if f.is_file():
                self.assertNotIn(SECRET, f.read_text(errors="replace"), str(f))

    def test_semgrep_secret_rules_are_secrets(self):
        gen = load_script("generate-report.py")
        self.put("run/r/semgrep.json", json.dumps({"results": [
            {"check_id": "generic.secrets.security.detected-aws-access-key-id-value.detected-aws-access-key-id-value",
             "path": "cfg.js", "start": {"line": 1}, "extra": {"severity": "ERROR", "message": "AWS key"}},
            {"check_id": "javascript.lang.security.audit.code-string-concat", "path": "a.js", "start": {"line": 2},
             "extra": {"severity": "WARNING", "message": "m", "metadata": {"category": "security"}}},
            {"check_id": "custom.leak", "path": "b.js", "start": {"line": 3},
             "extra": {"severity": "ERROR", "message": "m", "metadata": {"subcategory": ["secrets"]}}}]}))
        rows = gen.parse_semgrep("r", str(self.tmp / "run"), "/w")
        self.assertEqual([r["type"] for r in rows], ["secret", "sast", "secret"])

    def test_markdown_escapes_html(self):
        import report_formats
        md = report_formats.build_markdown([{"repo": "r", "scanner": "s", "type": "sast", "severity": "HIGH",
                                             "file": "a.js", "line": 1, "code": "<img src=x onerror=alert(1)>",
                                             "title": "<script>alert(1)</script>", "description": "<b>x</b>",
                                             "package": "", "installed_version": "", "fixed_version": "",
                                             "rule_id": "r", "url": ""}],
                                           {"team": "t", "org": "o", "repos": ["r"]})
        self.assertNotIn("<script>", md)
        self.assertNotIn("<b>", md)
        self.assertIn("`<img src=x onerror=alert(1)>`", md)  # inside a code span HTML is inert


class IssueBodyTests(unittest.TestCase):
    def test_mentions_and_html_neutralised(self):
        watch = load_script("advisory-watch.py")
        out = watch.neutralize("Ping @octocat and @org/team <img src=x> [x](javascript:alert(1))")
        self.assertNotIn("@octocat", out)
        self.assertNotIn("@org/team", out)
        self.assertNotIn("<img", out)
        self.assertNotIn("](javascript:", out)


@unittest.skipUnless(shutil.which("bash"), "bash required")
class ImageProbeTests(TempDirCase):
    def setUp(self):
        super(ImageProbeTests, self).setUp()
        self.bin = self.tmp / "bin"
        self.bin.mkdir()
        self.calls = self.tmp / "docker.log"
        stub = self.bin / "docker"
        stub.write_text('#!/usr/bin/env bash\necho "docker $*" >> "%s"\n'
                        'if [ "$1" = run ]; then echo "v22.14.0"; fi\nexit 0\n' % self.calls)
        stub.chmod(0o755)

    def env(self, **kw):
        e = dict(os.environ, PATH=str(self.bin) + os.pathsep + os.environ["PATH"], ADVISORY_OFFLINE="1",
                 JOB_SECURITY_SCAN_CACHE=str(self.tmp / "cache"), SECURITY_RUN_ROOT=str(self.tmp / "ws"))
        e.pop("JOB_SECURITY_SCAN_PROBE_IMAGES", None)
        e.update(kw)
        return e

    def run_scan(self, **env):
        (self.tmp / "ws").mkdir(exist_ok=True)
        cfg = self.put("repository.md", '---\nteam: t\norg: o\nmonorepo-root: "%s"\nrepos:\n'
                       '  - name: node-22-14-demo\n    active: true\n    has-dockerfile: true\n---\n' % FIX)
        return subprocess.run(["bash", str(RUN_SCAN), "--config", str(cfg), "--scanner", "advisories"],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True,
                              cwd=str(self.tmp / "ws"), env=self.env(**env))

    def test_images_not_run_by_default(self):
        r = self.run_scan()
        self.assertFalse(self.calls.exists() and "docker run" in self.calls.read_text(), r.stdout)
        self.assertIn("JOB_SECURITY_SCAN_PROBE_IMAGES", r.stdout)

    def test_opt_in_probe_is_sandboxed(self):
        self.run_scan(JOB_SECURITY_SCAN_PROBE_IMAGES="1")
        runs = [l for l in self.calls.read_text().splitlines() if l.startswith("docker run")]
        self.assertTrue(runs)
        for flag in ("--network none", "--read-only", "--cap-drop ALL", "--security-opt no-new-privileges",
                     "--pids-limit", "--memory", "--user 65534:65534"):
            self.assertIn(flag, runs[0])


if __name__ == "__main__":
    unittest.main()
