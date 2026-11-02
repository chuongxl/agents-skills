#!/usr/bin/env python3
"""Tests for verified findings: fingerprints, the v2 report schema and validator, changes since the last
run, run profiles and --since scope, and the triage queue/apply helper.

Run: python3 -I scripts/test-verification.py [TestClass ...] [-v]
No network, no scanner binaries. Stdlib only; Python 3.8+.
"""

import copy
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

VALIDATE = SKILL_DIR / "scripts" / "validate-report.py"
TRIAGE = SKILL_DIR / "scripts" / "triage.py"
GENERATE = SKILL_DIR / "scripts" / "generate-report.py"
RUN_SCAN = SKILL_DIR / "scripts" / "run-scan.sh"
FIX = SKILL_DIR / "tests" / "fixtures"
SECRET = "ghp_" + "VERIFYTESTVERIFYTESTVERIFYTEST123456"


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
    base = {"repo": "api", "scanner": "semgrep", "type": "sast", "severity": "HIGH", "file": "src/db.js",
            "line": 10, "code": "db.query('SELECT ' + id)", "package": "", "installed_version": "",
            "fixed_version": "", "rule_id": "sqli", "title": "SQL injection", "description": "d", "url": ""}
    base.update(kw)
    return base


def run(*args, **kw):
    return subprocess.run([sys.executable, "-I"] + [str(a) for a in args], stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, universal_newlines=True, **kw)


class FingerprintTests(unittest.TestCase):
    def setUp(self):
        import report_model
        self.fp = report_model.fingerprint

    def test_stable_when_code_moves_down_the_file(self):
        self.assertEqual(self.fp(finding(line=10)), self.fp(finding(line=42)))

    def test_changes_when_the_code_changes(self):
        self.assertNotEqual(self.fp(finding()), self.fp(finding(code="db.query('SELECT ' + other)")))

    def test_whitespace_does_not_matter(self):
        self.assertEqual(self.fp(finding(code="db.query( 'SELECT '  +  id )")),
                         self.fp(finding(code="db.query('SELECT ' + id)")))

    def test_dependency_keyed_by_package_version_not_line(self):
        a = finding(scanner="osv", type="vulnerability", file="yarn.lock", line=3, code="lodash@^4:",
                    package="lodash", installed_version="4.17.15", rule_id="GHSA-x")
        b = dict(a, line=99, code="lodash@^4.17.0:")
        c = dict(a, installed_version="4.17.21")
        self.assertEqual(self.fp(a), self.fp(b))
        self.assertNotEqual(self.fp(a), self.fp(c))

    def test_secret_fingerprint_never_uses_code(self):
        a = finding(scanner="gitleaks", type="secret", file=".env", line=3, code=SECRET, rule_id="github-pat")
        self.assertEqual(self.fp(a), self.fp(dict(a, code="")))
        self.assertNotEqual(self.fp(a), self.fp(dict(a, line=4)))

    def test_format(self):
        self.assertRegex(self.fp(finding()), r"^[0-9a-f]{16}$")


def v2_doc(findings=None):
    import report_model
    meta = {"team": "t", "org": "o", "config": "c", "run_dir": "/w/security-run-20261102-210000",
            "scanners": ["semgrep", "osv"], "repos": ["api"], "skipped": [],
            "generated_at": "2026-11-02T21:00:00+07:00", "profile": "standard", "since": None}
    rows = [finding(), finding(scanner="osv", type="vulnerability", file="yarn.lock", line=3, code="x",
                               package="lodash", installed_version="4.17.15", rule_id="GHSA-x", severity="MEDIUM")]
    return report_model.build_document(rows if findings is None else findings, meta, previous=None)


class ValidatorTests(TempDirCase):
    def validate(self, doc):
        import report_schema
        return report_schema.validate(doc)

    def test_generated_document_is_valid(self):
        doc = v2_doc()
        self.assertEqual(self.validate(doc), [])
        self.assertEqual(doc["schema_version"], 2)
        # standard profile queues CRITICAL+HIGH: the HIGH row is pending, the MEDIUM row is not queued
        self.assertEqual(doc["verification"]["queued"], 1)
        self.assertEqual(doc["verification"]["pending"], 1)
        self.assertTrue(all(f["change"] == "new" for f in doc["findings"]))
        self.assertEqual(doc["fixed"], [])

    def broken(self, mutate):
        doc = v2_doc()
        mutate(doc)
        return self.validate(doc)

    def test_rejects_each_broken_rule(self):
        def dup(d):
            d["findings"][1]["fingerprint"] = d["findings"][0]["fingerprint"]

        def bad_verdict(d):
            d["findings"][0]["verdict"] = "maybe"

        def rejected_without_reason(d):
            d["findings"][0].update(verdict="rejected", verdict_detail={})

        def nv_without_blocker(d):
            d["findings"][0].update(verdict="needs_validation", verdict_detail={"validation_plan": "x"})

        def confirmed_without_evidence(d):
            d["findings"][0].update(verdict="confirmed", verified_severity="HIGH",
                                    verdict_detail={"likelihood": "high", "impact": "high"})

        def severity_above_impact(d):
            d["findings"][0].update(verdict="confirmed", verified_severity="CRITICAL",
                                    verdict_detail={"evidence": "e", "likelihood": "high", "impact": "medium"})

        def code_on_secret(d):
            d["findings"][0].update(type="secret", code=SECRET)

        def wrong_counts(d):
            d["counts"]["HIGH"] += 5

        def bad_change(d):
            d["findings"][0]["change"] = "moved"

        def bad_severity(d):
            d["findings"][0]["severity"] = "SEVERE"

        for mutate in (dup, bad_verdict, rejected_without_reason, nv_without_blocker, confirmed_without_evidence,
                       severity_above_impact, code_on_secret, wrong_counts, bad_change, bad_severity):
            self.assertTrue(self.broken(mutate), mutate.__name__)

    def test_v1_document_reported_as_old_schema(self):
        errors = self.validate({"schema_version": 1, "findings": []})
        self.assertTrue(any("schema_version" in e for e in errors))

    def test_cli_exit_codes(self):
        good = self.put("good.json", json.dumps(v2_doc()))
        bad = self.put("bad.json", json.dumps({"schema_version": 2}))
        self.assertEqual(run(VALIDATE, good).returncode, 0)
        r = run(VALIDATE, bad)
        self.assertEqual(r.returncode, 1)
        self.assertIn("missing", r.stdout + r.stderr)
        self.assertEqual(run(VALIDATE, self.tmp / "missing.json").returncode, 2)

    def test_size_limit(self):
        big = self.put("big.json", " " * (6 * 1024 * 1024) + "{}")
        self.assertEqual(run(VALIDATE, big).returncode, 1)


if __name__ == "__main__":
    unittest.main()
