#!/usr/bin/env python3
"""Tests for stable fingerprints, the run-to-run diff and the baseline (scripts/lib/history.py),
including real run-scan.sh runs. Stdlib only:  python3 scripts/test-history.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "lib"))
import history  # noqa: E402
import report_formats  # noqa: E402

RUN_SCAN = HERE / "run-scan.sh"
FIX = HERE.parent / "tests" / "fixtures"


def finding(**kw):
    f = {"repo": "api", "scanner": "semgrep", "type": "code", "severity": "HIGH", "file": "src/a.js", "line": 10,
         "code": "eval(x)", "package": "", "installed_version": "", "fixed_version": "", "rule_id": "js.eval",
         "title": "eval", "description": "", "url": ""}
    f.update(kw)
    return f


class FingerprintTests(unittest.TestCase):
    def test_line_move_keeps_fingerprint(self):
        a = history.assign_fingerprints([finding(line=10)])[0]["fingerprint"]
        b = history.assign_fingerprints([finding(line=42, code="  eval(x)  ")])[0]["fingerprint"]
        self.assertEqual(a, b)
        self.assertTrue(a.startswith("semgrep:"))

    def test_file_rule_and_code_change_fingerprint(self):
        base = history.assign_fingerprints([finding()])[0]["fingerprint"]
        for change in ({"file": "src/b.js"}, {"rule_id": "js.other"}, {"code": "eval(y)"}, {"repo": "web"}):
            self.assertNotEqual(base, history.assign_fingerprints([finding(**change)])[0]["fingerprint"], change)

    def test_package_version_bump_keeps_fingerprint(self):
        vuln = dict(scanner="osv", type="vulnerability", file="yarn.lock", code="lodash@^4:", package="lodash",
                    rule_id="CVE-2020-8203")
        a = history.assign_fingerprints([finding(installed_version="4.17.19", line=5, **vuln)])[0]["fingerprint"]
        b = history.assign_fingerprints([finding(installed_version="4.17.20", line=9,
                                                 **dict(vuln, code="other"))])[0]["fingerprint"]
        self.assertEqual(a, b)

    def test_repeats_get_suffix_in_line_order(self):
        fs = history.assign_fingerprints([finding(type="secret", scanner="gitleaks", code=None, line=30),
                                          finding(type="secret", scanner="gitleaks", code=None, line=3)])
        by_line = dict((f["line"], f["fingerprint"]) for f in fs)
        self.assertTrue(by_line[30].endswith("-2"))
        self.assertFalse(by_line[3].endswith("-2"))

    def test_audit_fingerprint_is_the_record_fingerprint(self):
        f = history.assign_fingerprints([finding(scanner="audit", rule_id="notes-get-missing-owner-check")])[0]
        self.assertEqual(f["fingerprint"], "audit:notes-get-missing-owner-check")


class DiffTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(str(self.tmp), ignore_errors=True)

    def run_folder(self, name, findings, ran, schema=2):
        run = self.tmp / name
        run.mkdir()
        for repo, scanner in ran:
            raw = run / repo / history.RAW_OUTPUT[scanner]
            raw.parent.mkdir(parents=True, exist_ok=True)
            raw.write_text("[]")
        fs = [dict(f) for f in findings]
        if schema == 2:
            history.assign_fingerprints(fs)
        doc = {"schema_version": schema, "generated_at": name, "findings": fs}
        (run / "security-report.json").write_text(json.dumps(doc))
        return run

    def test_new_open_fixed(self):
        keep, gone = finding(), finding(file="src/old.js", rule_id="js.old")
        self.run_folder("security-run-20261101-100000", [keep, gone], {("api", "semgrep")})
        cur = self.run_folder("security-run-20261102-100000", [], {("api", "semgrep")})
        now = history.assign_fingerprints([finding(line=99), finding(file="src/new.js")])
        d = history.diff(now, str(cur), history.scanners_ran(str(cur)))
        status = dict((f["file"], f["diff_status"]) for f in now)
        self.assertEqual(status, {"src/a.js": "open", "src/new.js": "new"})
        self.assertEqual((d["new"], d["open"], d["fixed"]), (1, 1, 1))
        self.assertEqual(d["fixed_findings"][0]["file"], "src/old.js")
        self.assertEqual(now[0]["first_seen"], "security-run-20261101-100000")

    def test_narrow_run_does_not_mark_other_scanners_fixed(self):
        self.run_folder("security-run-20261101-100000", [finding(), finding(scanner="trivy", rule_id="CVE-1")],
                        {("api", "semgrep"), ("api", "trivy")})
        cur = self.run_folder("security-run-20261102-100000", [], {("api", "trivy")})
        d = history.diff([], str(cur), history.scanners_ran(str(cur)))
        self.assertEqual(d["fixed"], 1)              # trivy re-checked: its finding is fixed
        self.assertEqual(d["not_rechecked"], 1)      # semgrep did not run: not called fixed

    def test_pair_compared_with_latest_run_where_it_ran(self):
        self.run_folder("security-run-20261101-100000", [finding()], {("api", "semgrep")})
        self.run_folder("security-run-20261101-120000", [], {("api", "trivy")})   # semgrep did not run here
        cur = self.run_folder("security-run-20261102-100000", [], {("api", "semgrep")})
        now = history.assign_fingerprints([finding()])
        history.diff(now, str(cur), history.scanners_ran(str(cur)))
        self.assertEqual(now[0]["diff_status"], "open")

    def test_schema_v1_previous_report(self):
        old = finding()
        self.run_folder("security-run-20261101-100000", [old], {("api", "semgrep")}, schema=1)
        cur = self.run_folder("security-run-20261102-100000", [], {("api", "semgrep")})
        now = history.assign_fingerprints([finding()])
        d = history.diff(now, str(cur), history.scanners_ran(str(cur)))
        self.assertEqual((now[0]["diff_status"], d["fixed"]), ("open", 0))

    def test_first_scan(self):
        cur = self.run_folder("security-run-20261102-100000", [], {("api", "semgrep")})
        now = history.assign_fingerprints([finding()])
        d = history.diff(now, str(cur), history.scanners_ran(str(cur)))
        self.assertEqual((now[0]["diff_status"], d["compared_runs"]), ("first-scan", []))


class BaselineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(str(self.tmp), ignore_errors=True)

    def write(self, entries):
        p = self.tmp / "baseline.json"
        p.write_text(json.dumps({"version": 1, "entries": entries}))
        return str(p)

    def test_active_expired_invalid_unused(self):
        fs = history.assign_fingerprints([finding(), finding(file="src/b.js")])
        path = self.write([
            {"fingerprint": fs[0]["fingerprint"], "reason": "test code", "expires": "2099-01-01"},
            {"fingerprint": fs[1]["fingerprint"], "reason": "old", "expires": "2000-01-01"},
            {"fingerprint": "semgrep:deadbeefdeadbeef", "reason": "gone"},
            {"fingerprint": "x"},
            {"fingerprint": "y", "reason": "r", "expires": "soon"},
        ])
        b = history.load_baseline(path, today=date(2026, 11, 3))
        self.assertEqual(sorted(b["active"]), sorted([fs[0]["fingerprint"], "semgrep:deadbeefdeadbeef"]))
        self.assertEqual(len(b["expired"]), 1)
        self.assertEqual(len(b["invalid"]), 2)
        reported, accepted, unused = history.apply_baseline(fs, b)
        self.assertEqual([f["file"] for f in reported], ["src/b.js"])
        self.assertEqual(accepted[0]["baseline_reason"], "test code")
        self.assertEqual(unused, ["semgrep:deadbeefdeadbeef"])

    def test_unreadable_baseline_is_reported_not_fatal(self):
        p = self.tmp / "bad.json"
        p.write_text("{nope")
        b = history.load_baseline(str(p))
        self.assertEqual(b["active"], {})
        self.assertTrue(b["invalid"])

    def test_markdown_lists_accepted_and_excludes_from_counts(self):
        fs = history.assign_fingerprints([finding(severity="CRITICAL")])
        b = history.load_baseline(self.write([{"fingerprint": fs[0]["fingerprint"], "reason": "fixture"}]))
        reported, accepted, unused = history.apply_baseline(fs, b)
        meta = {"repos": ["api"], "baseline": {"path": "b.json", "accepted": accepted, "unused": unused,
                                               "expired": [], "invalid": []}}
        md = report_formats.build_markdown(reported, meta)
        doc = report_formats.build_json(reported, meta)
        self.assertIn("Accepted findings (baseline)", md)
        self.assertIn("fixture", md)
        self.assertEqual(doc["counts"]["CRITICAL"], 0)
        self.assertEqual(doc["baseline"]["accepted"][0]["baseline_reason"], "fixture")


@unittest.skipUnless(shutil.which("bash") and shutil.which("git"), "bash and git required")
class RunScanIntegrationTests(unittest.TestCase):
    """Two real runs of run-scan.sh (Shai-Hulud scanner, offline) over a copy of a fixture."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.ws = self.tmp / "ws"
        self.ws.mkdir()
        shutil.copytree(str(FIX / "shai-hulud" / "infected-lockfile"), str(self.ws / "app"))
        (self.tmp / "home").mkdir()
        self.cfg = self.ws / "repository.md"
        self.cfg.write_text('---\nteam: t\norg: o\nmonorepo-root: "."\nci-runner: x\nfail-on-severity: HIGH\n'
                            'repos:\n  - name: app\n    active: true\n    has-dockerfile: false\n---\n')

    def tearDown(self):
        shutil.rmtree(str(self.tmp), ignore_errors=True)

    def scan(self, *extra):
        env = dict(os.environ, HOME=str(self.tmp / "home"), XDG_CACHE_HOME=str(self.tmp / "xdg"),
                   SECURITY_RUN_ROOT=str(self.ws))
        env.pop("JOB_SECURITY_SCAN_CACHE", None)
        r = subprocess.run(["bash", str(RUN_SCAN), "--config", str(self.cfg), "--scanner", "shai-hulud"]
                           + list(extra), cwd=str(self.ws), env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           universal_newlines=True)
        run = sorted(p for p in self.ws.glob("security-run-*") if p.is_dir())[-1]
        return r, run, json.loads((run / "security-report.json").read_text())

    def test_open_then_fixed_then_baseline(self):
        r1, run1, doc1 = self.scan()
        self.assertEqual(r1.returncode, 2, r1.stdout + r1.stderr)
        self.assertTrue(doc1["findings"])
        self.assertTrue(all(f["diff_status"] == "first-scan" for f in doc1["findings"]))
        meta = json.loads((run1 / "run-metadata.json").read_text())
        self.assertEqual(meta["scanner"], "shai-hulud")
        self.assertIn("app", meta["source_refs"])

        r2, run2, doc2 = self.scan()
        self.assertTrue(all(f["diff_status"] == "open" for f in doc2["findings"]), doc2["findings"])
        self.assertEqual(doc2["diff"]["fixed"], 0)
        self.assertIn("Changes since last run", (run2 / "security-report.md").read_text())

        crit = [f["fingerprint"] for f in doc2["findings"] if f["severity"] in ("CRITICAL", "HIGH")]
        baseline = self.ws / "security-baseline.json"   # picked up automatically next to the config
        baseline.write_text(json.dumps({"version": 1, "entries": [
            {"fingerprint": fp, "reason": "test fixture"} for fp in crit]}))
        r3, run3, doc3 = self.scan()
        self.assertEqual(r3.returncode, 1, r3.stdout + r3.stderr)
        self.assertIn("downgraded to warning", r3.stdout)
        self.assertEqual(doc3["counts"]["CRITICAL"] + doc3["counts"]["HIGH"], 0)
        self.assertEqual(len(doc3["baseline"]["accepted"]), len(crit))
        baseline.unlink()

        (self.ws / "app" / "package-lock.json").unlink()
        r4, run4, doc4 = self.scan()
        self.assertGreaterEqual(doc4["diff"]["fixed"], 1, doc4["diff"])
        self.assertIn("Fixed since last run", (run4 / "security-report.md").read_text())
        self.assertIn("Fixed", (run4 / "security-report.html").read_text())

    def test_missing_baseline_file_is_an_error(self):
        env = dict(os.environ, HOME=str(self.tmp / "home"), SECURITY_RUN_ROOT=str(self.ws))
        r = subprocess.run(["bash", str(RUN_SCAN), "--config", str(self.cfg), "--scanner", "shai-hulud",
                            "--baseline", str(self.ws / "nope.json")], cwd=str(self.ws), env=env,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        self.assertEqual(r.returncode, 1)
        self.assertEqual(list(self.ws.glob("security-run-*")), [])


if __name__ == "__main__":
    unittest.main()
