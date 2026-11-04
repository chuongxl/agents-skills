#!/usr/bin/env python3
"""Tests for the deep audit inside the unified report: confirmed audit findings are ordinary v2 findings,
leads get their own section, an unfinished audit is never merged or treated as a re-check, and the baseline
(accepted findings) works with the report's fingerprints. Includes real run-scan.sh / generate-report.py runs.
Stdlib only:  python3 scripts/test-audit-report.py
"""
import importlib.util
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
import audit_report  # noqa: E402
import baseline  # noqa: E402
import report_schema  # noqa: E402

spec = importlib.util.spec_from_file_location("test_audit", str(HERE / "test-audit.py"))
ta = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ta)

GEN = HERE / "generate-report.py"
RUN_SCAN = HERE / "run-scan.sh"
CONFIG = ('---\nteam: t\norg: o\nmonorepo-root: "."\nci-runner: x\nfail-on-severity: HIGH\n'
          'repos:\n  - name: api\n    active: true\n    has-dockerfile: false\n---\n')


class Env(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.ws = self.tmp / "ws"
        (self.ws / "api" / "src").mkdir(parents=True)
        (self.ws / "api" / "src" / "app.js").write_text("\n".join("// line %d" % i for i in range(1, 60)) + "\n")
        (self.ws / "api" / "src" / "server.js").write_text("x\n" * 20)
        self.cfg = self.ws / "repository.md"
        self.cfg.write_text(CONFIG)

    def tearDown(self):
        shutil.rmtree(str(self.tmp), ignore_errors=True)

    def audit_dir(self, run):
        d = self.ws / run / "api" / "audit"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def write_audit(self, run, records, status="complete", ledger=True):
        d = self.audit_dir(run)
        (d / "run-metadata.json").write_text(json.dumps({
            "profile": "standard", "run_status": status, "execution_policy": "source-only",
            "source_ref": {"commit": "a" * 40, "dirty": True}}))
        if ledger:
            u = ta.unit(status="candidate", agent_id="h1", reviewed_paths=["src/app.js"],
                        local_checks=[ta.check()], result_fingerprints=["notes-get-missing-owner-check"])
            (d / "coverage-ledger.json").write_text(json.dumps([u]))
        (d / "findings.json").write_text(json.dumps(records))

    def generate(self, run, *extra):
        r = subprocess.run([sys.executable, "-I", str(GEN), "--results-dir", str(self.ws / run),
                            "--out-dir", str(self.ws / run), "--config", str(self.cfg), "--workspace", str(self.ws),
                            "--repos-root", str(self.ws), "--home", str(self.tmp)] + list(extra),
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return json.loads((self.ws / run / "security-report.json").read_text())


GOOD = lambda: sorted([ta.confirmed(), ta.needs_validation(), ta.rejected()], key=lambda r: r["fingerprint"])  # noqa


class MergeIntoReportTests(Env):
    def test_confirmed_finding_is_a_valid_v2_finding_and_leads_have_a_section(self):
        self.write_audit("security-run-20261103-100000", GOOD())
        doc = self.generate("security-run-20261103-100000")
        self.assertEqual(report_schema.validate(doc), [])
        rows = [f for f in doc["findings"] if f["scanner"] == "audit"]
        self.assertEqual(len(rows), 1)
        f = rows[0]
        self.assertEqual((f["severity"], f["verdict"], f["verified_severity"], f["file"], f["line"]),
                         ("HIGH", "confirmed", "HIGH", "src/app.js", 38))
        self.assertRegex(f["fingerprint"], r"^[0-9a-f]{16}$")
        self.assertEqual(f["verdict_detail"]["audit_fingerprint"], "notes-get-missing-owner-check")
        self.assertEqual(doc["counts"]["HIGH"], 1)
        self.assertEqual(doc["verification"]["confirmed"], 1)
        self.assertEqual(doc["verification"]["pending"], 0)
        self.assertEqual(len(doc["audit"]["api"]["needs_validation"]), 1)
        self.assertEqual(doc["run"]["coverage"]["api"]["audit"], "audit:standard")
        md = (self.ws / "security-run-20261103-100000" / "security-report.md").read_text()
        html = (self.ws / "security-run-20261103-100000" / "security-report.html").read_text()
        for text in (md, html):
            self.assertIn("Deep audit", text)
            self.assertIn("PR code runs with NPM_TOKEN", text)
        self.assertIn("Any user can read any note", md)

    def test_unfinished_or_invalid_audit_is_reported_but_not_merged(self):
        self.write_audit("security-run-20261103-100000", GOOD(), status="in_progress")
        doc = self.generate("security-run-20261103-100000")
        self.assertEqual(report_schema.validate(doc), [])
        self.assertFalse([f for f in doc["findings"] if f["scanner"] == "audit"])
        self.assertFalse(doc["audit"]["api"]["valid"])
        self.assertNotIn("audit", doc["run"]["coverage"]["api"])
        self.assertIn("run_status", (self.ws / "security-run-20261103-100000" / "security-report.md").read_text())

    def test_validator_rejects_inconsistent_audit_sections(self):
        self.write_audit("security-run-20261103-100000", GOOD())
        doc = self.generate("security-run-20261103-100000")
        bad = json.loads(json.dumps(doc))
        bad["audit"]["api"]["confirmed"] = 5
        self.assertTrue(any("confirmed" in e for e in report_schema.validate(bad)))
        bad = json.loads(json.dumps(doc))
        bad["audit"]["api"]["valid"] = False
        self.assertTrue(any("invalid audit" in e for e in report_schema.validate(bad)))
        bad = json.loads(json.dumps(doc))
        del bad["audit"]
        self.assertTrue(any("no audit section" in e for e in report_schema.validate(bad)))

    def test_next_run_marks_unchanged_and_fixed_only_after_a_valid_audit(self):
        self.write_audit("security-run-20261103-100000", GOOD())
        self.generate("security-run-20261103-100000")
        self.write_audit("security-run-20261103-110000", GOOD())
        doc2 = self.generate("security-run-20261103-110000")
        self.assertEqual([f["change"] for f in doc2["findings"] if f["scanner"] == "audit"], ["unchanged"])
        self.assertEqual(doc2["fixed"], [])
        # an audit that did not finish proves nothing: the finding must not be called fixed
        self.write_audit("security-run-20261103-120000", GOOD(), status="in_progress")
        doc3 = self.generate("security-run-20261103-120000")
        self.assertEqual(doc3["fixed"], [])
        # a complete audit that no longer confirms it: fixed
        self.write_audit("security-run-20261103-130000", [ta.needs_validation()])
        doc4 = self.generate("security-run-20261103-130000", "--previous",
                             str(self.ws / "security-run-20261103-110000"))
        self.assertEqual([x["scanner"] for x in doc4["fixed"]], ["audit"])
        # an audit of a different depth cannot call it fixed either
        self.write_audit("security-run-20261103-140000", [ta.needs_validation()])
        meta = self.ws / "security-run-20261103-140000" / "api" / "audit" / "run-metadata.json"
        m = json.loads(meta.read_text())
        m["profile"] = "deep"
        meta.write_text(json.dumps(m))
        doc5 = self.generate("security-run-20261103-140000", "--previous",
                             str(self.ws / "security-run-20261103-110000"))
        self.assertEqual(doc5["fixed"], [])

    def test_keep_verdicts_preserves_phase9_verdicts_when_regenerating(self):
        run = "security-run-20261103-100000"
        (self.ws / run / "api").mkdir(parents=True)
        (self.ws / run / "api" / "semgrep.json").write_text(json.dumps({"results": [{
            "check_id": "js.eval", "path": "src/app.js", "start": {"line": 5}, "end": {"line": 5},
            "extra": {"severity": "ERROR", "message": "eval", "lines": ""}}]}))
        doc = self.generate(run)
        sem = [f for f in doc["findings"] if f["scanner"] == "semgrep"][0]
        sem.update(verdict="rejected", verdict_detail={"reason": "test only"})
        import report_model
        report_model.refresh(doc)
        (self.ws / run / "security-report.json").write_text(json.dumps(doc))
        self.write_audit(run, GOOD())
        again = self.generate(run, "--keep-verdicts")
        by = dict((f["scanner"], f) for f in again["findings"])
        self.assertEqual(by["semgrep"]["verdict"], "rejected")
        self.assertEqual(by["audit"]["verdict"], "confirmed")
        self.assertEqual(report_schema.validate(again), [])
        lost = self.generate(run)
        self.assertIsNone([f for f in lost["findings"] if f["scanner"] == "semgrep"][0]["verdict"])


class BaselineTests(Env):
    def write_baseline(self, entries):
        p = self.ws / "security-baseline.json"
        p.write_text(json.dumps({"version": 1, "entries": entries}))
        return str(p)

    def test_accept_unused_expired_invalid(self):
        run = "security-run-20261103-100000"
        self.write_audit(run, GOOD())
        fp = [f for f in self.generate(run)["findings"] if f["scanner"] == "audit"][0]["fingerprint"]
        b = self.write_baseline([
            {"fingerprint": fp, "reason": "owner check tracked in TICKET-1", "owner": "sec"},
            {"fingerprint": "0" * 16, "reason": "stale"},
            {"fingerprint": "1" * 16, "reason": "old", "expires": "2020-01-01"},
            {"fingerprint": "nothex", "reason": "bad"}])
        doc = self.generate(run, "--baseline", b)
        self.assertEqual(report_schema.validate(doc), [])
        self.assertEqual(doc["counts"]["HIGH"], 0)
        self.assertFalse([f for f in doc["findings"] if f["scanner"] == "audit"])
        sec = doc["baseline"]
        self.assertEqual([a["fingerprint"] for a in sec["accepted"]], [fp])
        self.assertEqual(sec["unused"], ["0" * 16])
        self.assertEqual(len(sec["expired"]), 1)
        self.assertEqual(len(sec["invalid"]), 1)
        md = (self.ws / run / "security-report.md").read_text()
        self.assertIn("Accepted findings (baseline)", md)
        self.assertIn("TICKET-1", md)
        self.assertIn("matches no finding", md)
        self.assertIn("TICKET-1", (self.ws / run / "security-report.html").read_text())
        # the audit section still agrees with the (accepted) finding
        self.assertEqual(doc["audit"]["api"]["confirmed"], 1)

    def test_accepted_finding_is_not_called_fixed_and_stays_unchanged(self):
        self.write_audit("security-run-20261103-100000", GOOD())
        fp = [f for f in self.generate("security-run-20261103-100000")["findings"]
              if f["scanner"] == "audit"][0]["fingerprint"]
        b = self.write_baseline([{"fingerprint": fp, "reason": "accepted"}])
        self.write_audit("security-run-20261103-110000", GOOD())
        doc = self.generate("security-run-20261103-110000", "--baseline", b)
        self.assertEqual(doc["fixed"], [])
        self.write_audit("security-run-20261103-120000", GOOD())
        doc3 = self.generate("security-run-20261103-120000")      # baseline removed: back in the findings
        self.assertEqual([f["change"] for f in doc3["findings"] if f["scanner"] == "audit"], ["unchanged"])

    def test_load_rules(self):
        p = self.write_baseline([{"fingerprint": "a" * 16, "reason": "ok", "expires": "2026-12-31"},
                                 {"fingerprint": "b" * 16, "reason": " "}])
        b = baseline.load(p, today=date(2026, 11, 3))
        self.assertEqual(list(b["active"]), ["a" * 16])
        self.assertEqual(len(b["invalid"]), 1)
        self.assertEqual(baseline.load(str(self.ws / "none.json"))["invalid"][0]["entry"], None)


@unittest.skipUnless(shutil.which("bash") and shutil.which("git"), "bash and git required")
class RunScanTests(Env):
    def scan(self, *extra, env_extra=None):
        env = dict(os.environ, HOME=str(self.tmp / "home"), XDG_CACHE_HOME=str(self.tmp / "xdg"),
                   SECURITY_RUN_ROOT=str(self.ws))
        env.pop("JOB_SECURITY_SCAN_CACHE", None)
        env.pop("JOB_SECURITY_SCAN_AUDIT_EXEC", None)
        env.update(env_extra or {})
        (self.tmp / "home").mkdir(exist_ok=True)
        subprocess.run(["git", "init", "-q"], cwd=str(self.ws / "api"))
        r = subprocess.run(["bash", str(RUN_SCAN), "--config", str(self.cfg)] + list(extra), cwd=str(self.ws),
                           env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        runs = sorted(p for p in self.ws.glob("security-run-*") if p.is_dir())
        return r, (runs[-1] if runs else None)

    def test_scanner_audit_prepares_and_report_says_pending(self):
        r, run = self.scan("--scanner", "audit", "--profile", "quick", "--budget", "12")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        task = run / "api" / "audit" / "AGENT-TASK.md"
        self.assertTrue(task.is_file())
        self.assertIn("--keep-verdicts", task.read_text())
        meta = json.loads((run / "api" / "audit" / "run-metadata.json").read_text())
        self.assertEqual((meta["profile"], meta["budget"], meta["run_status"]), ("quick", 12, "awaiting_agent"))
        top = json.loads((run / "run-metadata.json").read_text())
        self.assertIn("api", top["source_refs"])
        doc = json.loads((run / "security-report.json").read_text())
        self.assertEqual(report_schema.validate(doc), [])
        self.assertIn("api", doc["run"]["source_refs"])
        self.assertFalse(doc["audit"]["api"]["valid"])
        self.assertIn("not written yet", " ".join(doc["audit"]["api"]["errors"]))
        self.assertIn("agent phase", r.stdout)

    def test_all_does_not_include_audit_without_the_flag(self):
        r, run = self.scan("--scanner", "shai-hulud")
        self.assertFalse((run / "api" / "audit").exists())
        r2, run2 = self.scan("--scanner", "shai-hulud", "--audit")
        self.assertTrue((run2 / "api" / "audit" / "AGENT-TASK.md").is_file())

    def test_bad_arguments(self):
        for args in (["--budget", "0"], ["--budget", "x"], ["--baseline", str(self.ws / "nope.json")]):
            r, run = self.scan(*args)
            self.assertEqual(r.returncode, 1, args)
        self.assertEqual(list(self.ws.glob("security-run-*")), [])

    def test_baseline_downgrades_a_failing_exit(self):
        shutil.copytree(str(HERE.parent / "tests" / "fixtures" / "shai-hulud" / "infected-lockfile"),
                        str(self.ws / "api"), dirs_exist_ok=True)
        r, run = self.scan("--scanner", "shai-hulud")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        doc = json.loads((run / "security-report.json").read_text())
        crit = [f["fingerprint"] for f in doc["findings"] if f["severity"] in ("CRITICAL", "HIGH")]
        self.assertTrue(crit)
        (self.ws / "security-baseline.json").write_text(json.dumps({"version": 1, "entries": [
            {"fingerprint": fp, "reason": "fixture"} for fp in crit]}))   # found next to the config
        r2, run2 = self.scan("--scanner", "shai-hulud")
        self.assertEqual(r2.returncode, 1, r2.stdout + r2.stderr)
        self.assertIn("downgraded to warning", r2.stdout)
        doc2 = json.loads((run2 / "security-report.json").read_text())
        self.assertEqual(doc2["counts"]["CRITICAL"] + doc2["counts"]["HIGH"], 0)
        self.assertEqual(report_schema.validate(doc2), [])


if __name__ == "__main__":
    unittest.main()
