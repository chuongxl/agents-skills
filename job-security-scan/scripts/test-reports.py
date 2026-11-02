#!/usr/bin/env python3
"""Offline tests for report generation: locating findings to file/line/code, the Markdown and
JSON writers, and the per-run security-run-* folder made by run-scan.sh.

Run: python3 -I scripts/test-reports.py [TestClass ...] [-v]
No network and no scanner binaries (scanners are stubbed on PATH). Stdlib only; Python 3.8+.
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

FIX = SKILL_DIR / "tests" / "fixtures"
RUN_SCAN = SKILL_DIR / "scripts" / "run-scan.sh"
GENERATE = SKILL_DIR / "scripts" / "generate-report.py"
NPM_TOKEN = "npm_" + "REPORTTESTTOKENREPORTTESTTOKEN0000"


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


def finding(**kw):
    base = {"repo": "r", "scanner": "x", "type": "vulnerability", "severity": "HIGH", "file": "", "line": None,
            "package": "", "installed_version": "", "fixed_version": "", "rule_id": "", "title": "t",
            "description": "", "url": "", "workspace": "/w"}
    base.update(kw)
    return base


NPM_LOCK = """{
  "name": "app",
  "lockfileVersion": 3,
  "packages": {
    "": {
      "name": "app",
      "dependencies": {
        "posthog-node": "^5.11.0"
      }
    },
    "node_modules/express": {
      "version": "4.21.2"
    },
    "node_modules/posthog-node": {
      "version": "5.11.3"
    }
  }
}
"""


class LocateTests(TempDirCase):
    def locate(self, f, home=None):
        from report_locate import locate
        return locate(f, self.tmp, home or self.tmp / "home")

    def test_keeps_given_line_and_reads_excerpt(self):
        self.put("src/app.js", "const a = 1;\nconst q = 'SELECT * FROM t WHERE id=' + id;\n")
        self.assertEqual(self.locate(finding(file="src/app.js", line=2, scanner="semgrep", type="sast")),
                         (2, "const q = 'SELECT * FROM t WHERE id=' + id;"))

    def test_npm_lock_v3_package_entry_line(self):
        self.put("package-lock.json", NPM_LOCK)
        line, code = self.locate(finding(file="package-lock.json", package="posthog-node", installed_version="5.11.3"))
        self.assertEqual(line, 14)
        self.assertEqual(code, '"node_modules/posthog-node": {')

    def test_yarn_lock_line(self):
        self.put("yarn.lock", '# yarn lockfile v1\n\nexpress@^4.0.0:\n  version "4.21.2"\n\nlodash@^4.17.0:\n'
                              '  version "4.17.20"\n')
        self.assertEqual(self.locate(finding(file="yarn.lock", package="lodash", installed_version="4.17.20"))[0], 6)

    def test_requirements_line(self):
        self.put("requirements.txt", "flask==3.0.0\ndjango==2.2.0\n")
        self.assertEqual(self.locate(finding(file="requirements.txt", package="Django", installed_version="2.2.0")),
                         (2, "django==2.2.0"))

    def test_absolute_path_file(self):
        p = self.put("deep/go.mod", "module x\n\nrequire golang.org/x/text v0.3.2\n")
        self.assertEqual(self.locate(finding(file=str(p), package="golang.org/x/text", installed_version="0.3.2"))[0], 3)

    def test_marker_evidence_line(self):
        self.put(".github/workflows/discussion.yaml",
                 "name: d\non:\n  discussion:\njobs:\n  p:\n    steps: []\n    runs-on: [self-hosted, SHA1HULUD]\n")
        f = finding(scanner="shai-hulud", type="supply-chain", file=".github/workflows/discussion.yaml",
                    rule_id="marker", evidence="SHA1HULUD")
        self.assertEqual(self.locate(f), (7, "runs-on: [self-hosted, SHA1HULUD]"))

    def test_file_finding_without_anchor_is_line_1(self):
        self.put("node_modules/p/setup_bun.js", "// stand-in\n")
        f = finding(scanner="shai-hulud", type="supply-chain", file="node_modules/p/setup_bun.js", rule_id="payload-file")
        self.assertEqual(self.locate(f), (1, "// stand-in"))

    def test_non_manifest_file_with_package_falls_back_to_line_1(self):
        self.put("node_modules/p/bun_environment.js", "// stand-in payload\n")
        f = finding(scanner="shai-hulud", type="supply-chain", file="node_modules/p/bun_environment.js",
                    rule_id="payload-file", package="@scope/victim-lib", installed_version="1.0.0")
        self.assertEqual(self.locate(f), (1, "// stand-in payload"))

    def test_lockfile_without_the_package_stays_null(self):
        self.put("package-lock.json", NPM_LOCK)
        self.assertEqual(self.locate(finding(file="package-lock.json", package="absent", installed_version="1.0.0")),
                         (None, ""))

    def test_secret_row_gets_line_but_no_code(self):
        self.put(".env", "API_KEY=%s\n" % NPM_TOKEN)
        self.assertEqual(self.locate(finding(file=".env", line=1, type="secret", scanner="gitleaks")), (1, ""))

    def test_credential_rows_never_opened(self):
        home = self.tmp / "home"
        self.put("home/.npmrc", "//registry.npmjs.org/:_authToken=%s\n" % NPM_TOKEN)
        for rule in ("credential-store", "credential-permissions"):
            f = finding(repo="this machine", scanner="shai-hulud", type="supply-chain", file="~/.npmrc", rule_id=rule)
            self.assertEqual(self.locate(f, home), (None, ""), rule)

    def test_home_relative_path(self):
        home = self.tmp / "home"
        self.put("home/proj/package-lock.json", NPM_LOCK)
        f = finding(repo="this machine", file="~/proj/package-lock.json", package="posthog-node", installed_version="5.11.3")
        self.assertEqual(self.locate(f, home)[0], 14)

    def test_missing_or_binary_file_returns_null(self):
        self.assertEqual(self.locate(finding(file="nope.lock", package="x", installed_version="1")), (None, ""))
        (self.tmp / "bin.dat").write_bytes(b"\x00\x01\x02" * 50)
        self.assertEqual(self.locate(finding(file="bin.dat", line=3)), (3, ""))
        self.assertEqual(self.locate(finding(file="")), (None, ""))

    def test_excerpt_redacted_and_capped(self):
        self.put("cfg.js", "const token = '%s'; %s\n" % (NPM_TOKEN, "x" * 300))
        line, code = self.locate(finding(file="cfg.js", line=1, type="sast", scanner="semgrep"))
        self.assertEqual(line, 1)
        self.assertNotIn(NPM_TOKEN, code)
        self.assertLessEqual(len(code), 160)

    def test_apply_sets_fields_in_place(self):
        from report_locate import apply
        self.put("r/package-lock.json", NPM_LOCK)
        rows = [finding(repo="r", file="package-lock.json", package="posthog-node", installed_version="5.11.3")]
        apply(rows, self.tmp, self.tmp / "home")
        self.assertEqual((rows[0]["line"], rows[0]["code"]), (14, '"node_modules/posthog-node": {'))


META = {"team": "acme", "org": "acme-org", "config": "repository.md", "run_dir": "/w/security-run-20261102-153600",
        "scanners": ["osv", "shai-hulud", "gitleaks"], "repos": ["api", "web", "worker"], "skipped": [],
        "generated_at": "2026-11-02T15:36:00+07:00"}


def rows():
    return [
        finding(repo="api", scanner="shai-hulud", type="supply-chain", severity="CRITICAL", file="package-lock.json",
                line=14, code='"node_modules/posthog-node": {', package="posthog-node", installed_version="5.11.3",
                rule_id="known-package", title="Known compromised npm release"),
        finding(repo="api", scanner="gitleaks", type="secret", severity="HIGH", file=".env", line=3, code="",
                rule_id="generic-api-key", title="Secret | in `.env`"),
        finding(repo="web", scanner="osv", type="vulnerability", severity="MEDIUM", file="yarn.lock", line=6,
                code="lodash@^4.17.0:", package="lodash", installed_version="4.17.20", fixed_version="4.17.21",
                rule_id="CVE-2020-8203", title="Prototype pollution"),
    ]


class FormatTests(unittest.TestCase):
    def setUp(self):
        import report_formats
        self.rf = report_formats

    def test_json_shape_and_counts(self):
        doc = self.rf.build_json(rows(), META)
        self.assertEqual(doc["schema_version"], 1)
        self.assertEqual(doc["counts"], {"CRITICAL": 1, "HIGH": 1, "MEDIUM": 1, "LOW": 0, "INFO": 0})
        by = {r["name"]: r for r in doc["repos"]}
        self.assertEqual((by["api"]["status"], by["web"]["status"], by["worker"]["status"]), ("red", "yellow", "green"))
        f0 = doc["findings"][0]
        self.assertEqual((f0["file"], f0["line"], f0["code"]), ("package-lock.json", 14, '"node_modules/posthog-node": {'))
        self.assertNotIn("workspace", f0)

    def test_markdown_sections_and_file_line(self):
        md = self.rf.build_markdown(rows(), META)
        for heading in ("# Security Scan Report — acme / acme-org", "## Summary", "## 🔴 Critical Findings",
                        "## 🟡 Medium Findings", "## 🔑 Secrets (values never shown)", "## 📋 Remediation guidance"):
            self.assertIn(heading, md)
        self.assertIn("`package-lock.json:14`", md)
        self.assertIn('`"node_modules/posthog-node": {`', md)
        self.assertIn("| worker | 0 | 0 | 0 | 0 | 0 | 🟢 |", md)
        self.assertIn("security-run-20261102-153600", md)

    def test_markdown_secret_has_no_code(self):
        md = self.rf.build_markdown(rows(), META)
        secrets = md.split("## 🔑 Secrets (values never shown)")[1].split("\n## ")[0]
        self.assertIn("`.env:3`", secrets)
        self.assertNotIn("    `", secrets)

    def test_markdown_never_offers_fixes(self):
        md = self.rf.build_markdown(rows(), META).lower()
        for phrase in ("would you like", "shall i", "i can fix", "let me fix", "apply the fix"):
            self.assertNotIn(phrase, md)

    def test_markdown_escapes_pipes_backticks(self):
        md = self.rf.build_markdown(rows(), META)
        self.assertIn("Secret \\| in", md)
        self.assertNotIn("in `.env``", md)

    def test_clean_run_reports(self):
        md = self.rf.build_markdown([], META)
        self.assertIn("No findings", md)
        self.assertEqual(self.rf.build_json([], META)["counts"]["CRITICAL"], 0)


class GenerateTests(TempDirCase):
    def test_out_dir_writes_three_files(self):
        res, src, out = self.tmp / "run", self.tmp / "repos", self.tmp / "run"
        self.put("repos/api/src/db.js", "const a = 1;\nconst q = 'SELECT ' + id;\n")
        lock = self.put("repos/api/yarn.lock", '# yarn lockfile v1\n\nlodash@^4.17.0:\n  version "4.17.20"\n')
        self.put("run/api/semgrep.json", json.dumps({"results": [{"check_id": "sqli", "path": "src/db.js",
                 "start": {"line": 2}, "extra": {"severity": "ERROR", "message": "SQL injection"}}]}))
        self.put("run/api/osv.json", json.dumps({"results": [{"source": {"path": str(lock)}, "packages": [{
            "package": {"name": "lodash", "version": "4.17.20"},
            "vulnerabilities": [{"id": "GHSA-x", "aliases": ["CVE-2020-8203"], "summary": "Prototype pollution"}]}]}]}))
        cfg = self.put("repository.md", "---\nteam: acme\norg: acme-org\nrepos:\n  - name: api\n    active: true\n---\n")
        r = subprocess.run([sys.executable, "-I", str(GENERATE), "--results-dir", str(res), "--config", str(cfg),
                            "--out-dir", str(out), "--repos-root", str(src), "--home", str(self.tmp / "home"),
                            "--workspace", str(self.tmp)],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        md = (out / "security-report.md").read_text()
        doc = json.loads((out / "security-report.json").read_text())
        page = (out / "security-report.html").read_text()
        self.assertIn("`src/db.js:2`", md)
        self.assertIn("`const q = 'SELECT ' + id;`", md)
        self.assertIn("yarn.lock:3", md)
        osv = [f for f in doc["findings"] if f["scanner"] == "osv"][0]
        self.assertEqual((osv["line"], osv["code"]), (3, "lodash@^4.17.0:"))
        self.assertIn("db.js:2", page)
        self.assertIn("SELECT", page)

    def test_real_osv_v2_output_with_cvss_vectors(self):
        """osv-scanner v2 shape: CVSS scores are vector strings; severity comes from groups[].max_severity."""
        lock = self.put("repos/api/yarn.lock", '# yarn lockfile v1\n\nlodash@^4.17.0:\n  version "4.17.15"\n')
        vulns = [
            {"id": "GHSA-p6mc-m468-83gw", "aliases": ["CVE-2020-8203"], "summary": "Prototype Pollution in lodash",
             "severity": [{"type": "CVSS_V3", "score": "CVSS:3.1/AV:N/AC:H/PR:N/UI:N/S:U/C:N/I:H/A:H"}],
             "database_specific": {"severity": "HIGH"}},
            {"id": "GHSA-29mw-wpgm-hmr9", "aliases": ["CVE-2020-28500"], "summary": "ReDoS in lodash",
             "severity": [{"type": "CVSS_V3", "score": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:L"}],
             "database_specific": {"severity": "MODERATE"}},
            {"id": "GHSA-35jh-r3h4-6jhm", "summary": "Command Injection in lodash", "severity": []},
        ]
        osv = {"results": [{"source": {"path": str(lock), "type": "lockfile"}, "packages": [{
            "package": {"name": "lodash", "version": "4.17.15", "ecosystem": "npm"}, "vulnerabilities": vulns,
            "groups": [{"ids": ["GHSA-p6mc-m468-83gw", "CVE-2020-8203"], "max_severity": "7.4"},
                       {"ids": ["GHSA-29mw-wpgm-hmr9"], "max_severity": "5.3"},
                       {"ids": ["GHSA-35jh-r3h4-6jhm"], "max_severity": "9.8"}]}]}]}
        self.put("run/api/osv.json", json.dumps(osv))
        cfg = self.put("repository.md", "---\nteam: acme\norg: acme-org\n---\n")
        r = subprocess.run([sys.executable, "-I", str(GENERATE), "--results-dir", str(self.tmp / "run"),
                            "--config", str(cfg), "--out-dir", str(self.tmp / "run"),
                            "--repos-root", str(self.tmp / "repos")],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        rows = json.loads((self.tmp / "run" / "security-report.json").read_text())["findings"]
        sev = dict((f["rule_id"], f["severity"]) for f in rows)
        self.assertEqual(sev, {"GHSA-p6mc-m468-83gw": "HIGH", "GHSA-29mw-wpgm-hmr9": "MEDIUM",
                               "GHSA-35jh-r3h4-6jhm": "CRITICAL"})
        self.assertTrue(all(f["line"] == 3 for f in rows), rows)

    def test_one_broken_scanner_output_does_not_kill_the_report(self):
        self.put("run/api/osv.json", json.dumps({"results": [{"source": {"path": "x"}, "packages": [
            {"package": {"name": "p", "version": "1"}, "vulnerabilities": [{"id": "X-1", "severity": "weird"}],
             "groups": "also weird"}]}]}))
        self.put("run/api/semgrep.json", json.dumps({"results": [{"check_id": "r", "path": "a.js",
                 "start": {"line": 1}, "extra": {"severity": "ERROR", "message": "m"}}]}))
        cfg = self.put("repository.md", "---\nteam: acme\norg: acme-org\n---\n")
        r = subprocess.run([sys.executable, "-I", str(GENERATE), "--results-dir", str(self.tmp / "run"),
                            "--config", str(cfg), "--out-dir", str(self.tmp / "run")],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        rows = json.loads((self.tmp / "run" / "security-report.json").read_text())["findings"]
        self.assertIn("semgrep", {f["scanner"] for f in rows})

    def test_failure_exits_non_zero(self):
        r = subprocess.run([sys.executable, "-I", str(GENERATE), "--results-dir", str(self.tmp), "--config",
                            str(self.tmp / "missing.md"), "--out-dir", str(self.tmp / "o")],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        self.assertNotEqual(r.returncode, 0)


SH_FIX = FIX / "shai-hulud"


def run_dirs(root):
    return sorted(p for p in Path(root).glob("security-run-*") if p.is_dir())


@unittest.skipUnless(shutil.which("bash"), "bash required")
class RunFolderTests(TempDirCase):
    def setUp(self):
        super(RunFolderTests, self).setUp()
        self.ws = self.tmp / "ws"
        self.ws.mkdir()
        self.bin = self.tmp / "bin"
        self.bin.mkdir()
        self.calls = self.tmp / "calls.log"
        gitleaks = ('#!/usr/bin/env bash\necho "gitleaks $*" >> "%s"\nout=""; prev=""\n'
                    'for a in "$@"; do [ "$prev" = "--report-path" ] && out="$a"; prev="$a"; done\n'
                    '[ -n "$out" ] && echo "[]" > "$out"\nexit 0\n' % self.calls)
        g = self.bin / "gitleaks"
        g.write_text(gitleaks)
        g.chmod(0o755)

    def config(self, extra="", repos=("infected-lockfile", "clean"), root=SH_FIX):
        body = "".join("  - name: %s\n    active: true\n    has-dockerfile: false\n" % n for n in repos)
        return self.put("ws/repository.md", '---\nteam: t\norg: o\nmonorepo-root: "%s"\nci-runner: x\n'
                        'fail-on-severity: HIGH\n%srepos:\n%s---\n' % (root, extra, body))

    def run_scan(self, *args, env=None, run_root=True):
        e = dict(os.environ, PATH=str(self.bin) + os.pathsep + os.environ["PATH"],
                 XDG_CACHE_HOME=str(self.tmp / "xdg"), HOME=str(self.tmp / "home"), NPM_CONFIG_PREFIX="")
        e.pop("JOB_SECURITY_SCAN_CACHE", None)
        if run_root:
            e["SECURITY_RUN_ROOT"] = str(self.ws)
        e.update(env or {})
        (self.tmp / "home").mkdir(exist_ok=True)
        return subprocess.run(["bash", str(RUN_SCAN)] + [str(a) for a in args], stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, universal_newlines=True, cwd=str(self.ws), env=e)

    def test_run_folder_with_three_reports_and_raw(self):
        r = self.run_scan("--config", self.config(), "--scanner", "shai-hulud")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        runs = run_dirs(self.ws)
        self.assertEqual(len(runs), 1)
        self.assertRegex(runs[0].name, r"^security-run-\d{8}-\d{6}$")
        for name in ("security-report.md", "security-report.json", "security-report.html", ".gitignore",
                     "infected-lockfile/shai-hulud.json", "clean/shai-hulud.json"):
            self.assertTrue((runs[0] / name).is_file(), name)
        self.assertEqual((runs[0] / ".gitignore").read_text().strip(), "*")
        doc = json.loads((runs[0] / "security-report.json").read_text())
        hit = [f for f in doc["findings"] if f["rule_id"] == "known-package"][0]
        self.assertEqual((hit["file"], hit["line"]), ("package-lock.json", 6))
        self.assertIn("node_modules/@accordproject/concerto-linter", hit["code"])
        self.assertIn("Run folder: %s" % runs[0], r.stdout)

    def test_workspace_has_only_run_folder(self):
        r = self.run_scan("--config", self.config(), "--scanner", "shai-hulud", run_root=False)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        names = sorted(p.name for p in self.ws.iterdir() if p.name != "repository.md")
        self.assertEqual(len(names), 1, names)
        self.assertTrue(names[0].startswith("security-run-"))

    def test_cache_dir_precedence(self):
        demo = ("node-22-14-demo",)
        cases = [
            ({"JOB_SECURITY_SCAN_CACHE": str(self.tmp / "envcache")}, 'cache-dir: "%s"\n' % (self.tmp / "cfgcache"),
             self.tmp / "envcache", False),
            ({}, 'cache-dir: "%s"\n' % (self.tmp / "cfgcache"), self.tmp / "cfgcache", False),
            ({}, 'output-dir: "%s"\n' % (self.tmp / "legacy"), self.tmp / "legacy", True),
            ({}, "", self.tmp / "xdg" / "job-security-scan", False),
        ]
        for env, extra, expected, warns in cases:
            env = dict(env, ADVISORY_OFFLINE="1")
            r = self.run_scan("--config", self.config(extra, repos=demo, root=FIX), "--scanner", "advisories", env=env)
            self.assertTrue((expected / "advisories").is_dir(), (expected, r.stdout + r.stderr))
            self.assertEqual("output-dir" in r.stderr and "deprecated" in r.stderr, warns, r.stderr)

    def test_same_second_gets_suffix(self):
        date = self.bin / "date"
        date.write_text('#!/usr/bin/env bash\nif [ "$1" = "+%Y%m%d-%H%M%S" ]; then echo 20261102-153600; '
                        'else exec /bin/date "$@"; fi\n')
        date.chmod(0o755)
        (self.ws / "security-run-20261102-153600").mkdir()
        (self.ws / "security-run-20261102-153600" / "keep.txt").write_text("first run")
        self.run_scan("--config", self.config(repos=("clean",)), "--scanner", "shai-hulud")
        self.assertTrue((self.ws / "security-run-20261102-153600-2" / "security-report.md").is_file())
        self.assertEqual(sorted(p.name for p in (self.ws / "security-run-20261102-153600").iterdir()), ["keep.txt"])

    def test_host_only_and_clean_run_still_write_reports(self):
        r = self.run_scan("--host")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        r = self.run_scan("--config", self.config(repos=("clean",)), "--scanner", "shai-hulud")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        runs = run_dirs(self.ws)
        self.assertEqual(len(runs), 2)
        for run in runs:
            for name in ("security-report.md", "security-report.json", "security-report.html"):
                self.assertTrue((run / name).is_file(), (run, name))
        self.assertIn("No findings", (runs[-1] / "security-report.md").read_text())

    def test_gitleaks_called_with_redact(self):
        self.run_scan("--config", self.config(repos=("clean",)), "--scanner", "gitleaks")
        self.assertIn("--redact", self.calls.read_text())

    def test_unknown_scanner_creates_no_folder(self):
        r = self.run_scan("--config", self.config(), "--scanner", "nope")
        self.assertEqual(r.returncode, 1)
        self.assertEqual(run_dirs(self.ws), [])


if __name__ == "__main__":
    unittest.main()
