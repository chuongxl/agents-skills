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


if __name__ == "__main__":
    unittest.main()
