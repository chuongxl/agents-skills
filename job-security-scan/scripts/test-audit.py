#!/usr/bin/env python3
"""Tests for the deep audit (Phase 9): findings/ledger validators, coverage IDs, ledger seeding, preparation,
report merge gating, sandbox and evidence promotion. Stdlib only:  python3 scripts/test-audit.py
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

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "lib"))
import audit  # noqa: E402
import audit_report  # noqa: E402

FIX = HERE.parent / "tests" / "fixtures"
PY = sys.executable


def trace():
    return [{"kind": "entrypoint", "file": "src/server.js", "line": 9, "scope": "request handler",
             "description": "path from the request"},
            {"kind": "sink", "file": "src/app.js", "line": 38, "scope": "route GET /notes/:id",
             "description": "returns the note without an owner check"}]


def confirmed(fp="notes-get-missing-owner-check"):
    return {
        "verdict": "confirmed", "fingerprint": fp, "title": "Any user can read any note",
        "description": "GET /notes/:id returns notes of other users.",
        "root_cause": "The GET branch never compares note.owner with the caller.",
        "intended_behavior": "Only the owner can read a note, as DELETE enforces.",
        "trace": trace(),
        "evidence": [{"file": "src/app.js", "line": 46, "description": "DELETE checks note.owner !== user"}],
        "conditions": [{"kind": "authentication_level", "description": "any valid bearer token"}],
        "execution": {"attacker_perspective": "authenticated user bob",
                      "payloads": ["route('GET', '/notes/1', {authorization: 'Bearer token-bob'})"],
                      "instructions": ["call route() with bob's token for alice's note id"],
                      "observed_result": "status 200 with alice's note text"},
        "remediation": {"strategy": "Return 404 unless note.owner === user, like DELETE."},
        "severity": {"likelihood": {"score": "high", "reason": "any user, sequential ids"},
                     "impact": {"score": "high", "reason": "cross-user read of private notes"},
                     "overall_severity": "high"},
        "confidence": {"score": "high", "reason": "reproduced locally"},
    }


def needs_validation(fp="ci-pull-request-target-token"):
    return {
        "verdict": "needs_validation", "fingerprint": fp, "title": "PR code runs with NPM_TOKEN",
        "description": "pull_request_target checks out the PR head and runs npm test with a token.",
        "claimed_root_cause": "untrusted checkout in a privileged workflow",
        "trace": [{"kind": "sink", "file": ".github/workflows/ci.yml", "line": 14, "scope": "job test",
                   "description": "npm test with NPM_TOKEN"}],
        "evidence": [{"file": ".github/workflows/ci.yml", "line": 4, "description": "pull_request_target"}],
        "blockers": ["whether fork PRs require maintainer approval is a repository setting"],
        "validation_plan": {"deployment": "Owner checks Settings > Actions > fork PR approval."},
    }


def rejected(fp="version-exec-injection"):
    return {
        "verdict": "rejected", "fingerprint": fp, "title": "Command injection in /version",
        "description": "execFileSync in a route", "claimed_root_cause": "request data in a command",
        "trace": [{"kind": "sink", "file": "src/app.js", "line": 54, "scope": "GET /version",
                   "description": "execFileSync with a fixed argv"}],
        "evidence": [{"file": "src/app.js", "line": 54, "description": "no request data, no shell"}],
        "reason": "Fixed argument list; no request input reaches the call.",
    }


def unit(**kw):
    spec = {"surface": "GET /notes/:id", "boundary": "owner check", "subsystem": "src",
            "attack_class": "Access control",
            "canonical_refs": {"surface": "src/app.js#GET /notes/:id", "boundary": "src/app.js#route owner check",
                               "subsystem": "src", "attack_class": "ATTACK-CLASSES.md#Access control"},
            "starting_paths": ["src/app.js"], "ordinary_attack_class_block": "ATTACK-CLASSES.md#Access control"}
    u = audit.new_unit(spec)
    u.update(kw)
    return u


def check(agent="h1", method="source", artifact=None, paths=("src/app.js",)):
    return {"agent_id": agent, "reviewed_paths": list(paths), "invariant": "owner bound to caller",
            "method": method, "result": "GET has no owner check", "artifact": artifact}


class FindingsValidatorTests(unittest.TestCase):
    def ok(self, doc):
        self.assertEqual(audit.validate_findings(doc), [])

    def bad(self, doc, needle):
        errors = audit.validate_findings(doc)
        self.assertTrue(any(needle in e for e in errors), errors)

    def test_schema_uses_only_supported_keywords(self):
        self.assertEqual(audit.check_schema(audit.load_schema()), [])

    def test_valid_three_verdicts_sorted(self):
        self.ok(sorted([confirmed(), needs_validation(), rejected()], key=lambda r: r["fingerprint"]))
        self.ok([])

    def test_needs_validation_cannot_have_severity(self):
        r = needs_validation()
        r["severity"] = confirmed()["severity"]
        self.bad([r], "must match exactly one schema in oneOf")

    def test_overall_cannot_exceed_impact(self):
        r = confirmed()
        r["severity"]["overall_severity"] = "critical"
        self.bad([r], "cannot exceed demonstrated impact")

    def test_sorted_and_unique(self):
        self.bad([confirmed("b"), confirmed("a")], "sorted lexicographically")
        self.bad([confirmed("a"), confirmed("a")], "duplicate")

    def test_trace_shape(self):
        r = confirmed()
        r["trace"][0]["kind"] = "propagation"
        self.bad([r], 'must be "entrypoint"')
        r = needs_validation()
        r["trace"][0]["kind"] = "propagation"
        self.bad([r], "one-line trace")

    def test_unsafe_paths(self):
        for path in ("/etc/passwd", "../x.js", "C:/x.js", "src/./a.js", "~/a", "src/con.js", "a\\b.js"):
            r = confirmed()
            r["trace"][1]["file"] = path
            self.bad([r], "safe repository-relative source path")

    def test_missing_plan_and_invisible_text(self):
        r = needs_validation()
        r["validation_plan"] = {"local": " \u200b "}
        self.bad([r], "")
        r = confirmed()
        r["title"] = "\u200b"
        self.bad([r], "")

    def test_extra_field_rejected(self):
        r = confirmed()
        r["proposed_verdict"] = "confirmed"
        self.bad([r], "")

    def test_odd_types_never_crash(self):
        junk = (None, 0, 1.5, True, "x", [], {}, [1], {"a": 1})
        for value in junk:
            for doc_fn in (confirmed, needs_validation, rejected):
                for key in list(doc_fn()):
                    r = doc_fn()
                    r[key] = value
                    self.assertTrue(isinstance(audit.validate_findings([r]), list))
            for key in list(unit()):
                u = unit()
                u[key] = value
                self.assertTrue(isinstance(audit.validate_ledger([u]), list))
                u = unit(status="covered", agent_id="h1", reviewed_paths=["src/app.js"], local_checks=[check()])
                u["local_checks"][0]["agent_id"] = value
                audit.validate_ledger([u])

    def test_fingerprint_pattern(self):
        self.bad([confirmed("-bad")], "")
        self.bad([confirmed("has space")], "")


class LedgerTests(unittest.TestCase):
    def test_coverage_id_encoding(self):
        refs = {"surface": "src/app.js#GET /notes/:id", "boundary": "b", "subsystem": "src",
                "attack_class": "ATTACK-CLASSES.md#Access control"}
        self.assertEqual(audit.coverage_id(refs),
                         "src%2Fapp.js%23GET%20%2Fnotes%2F%3Aid::b::src::ATTACK-CLASSES.md%23Access%20control")
        self.assertEqual(audit.coverage_id(dict(refs, surface="é")), "%C3%A9::b::src::"
                         "ATTACK-CLASSES.md%23Access%20control")
        for bad in (" lead", "a\u200bb", "e\u0301"):   # whitespace, default-ignorable, not NFC
            with self.assertRaises(ValueError):
                audit.coverage_id(dict(refs, surface=bad))

    def test_states(self):
        self.assertEqual(audit.validate_ledger([unit()]), [])
        good = [unit(status="candidate", agent_id="h1", reviewed_paths=["src/app.js"], local_checks=[check()],
                     result_fingerprints=["notes-get-missing-owner-check"]),
                unit(status="covered", agent_id="h1", reviewed_paths=["src/app.js"], local_checks=[check()]),
                unit(status="deferred", unresolved=["budget_cannot_reserve_critics_and_validation"])]
        for u in good:
            self.assertEqual(audit.validate_ledger([u]), [], u["status"])
        bad = [unit(agent_id="h1"),
               unit(status="covered", agent_id="h1"),
               unit(status="candidate", agent_id="h1", reviewed_paths=["src/app.js"], local_checks=[check()]),
               unit(status="deferred"),
               unit(status="covered", agent_id="H1", reviewed_paths=["src/app.js"], local_checks=[check()]),
               unit(status="covered", agent_id="h1", reviewed_paths=["src/app.js", "src/x.js"],
                    local_checks=[check()])]
        for u in bad:
            self.assertTrue(audit.validate_ledger([u]), u)

    def test_local_check_artifact_ownership(self):
        u = unit(status="covered", agent_id="h1", reviewed_paths=["src/app.js"],
                 local_checks=[check(method="local", artifact="agents/h1/artifacts/out.txt")])
        self.assertEqual(audit.validate_ledger([u]), [])
        for art in ("agents/h2/artifacts/out.txt", "agents/h1/scratch/out.txt", None):
            u["local_checks"][0]["artifact"] = art
            self.assertTrue(audit.validate_ledger([u]), art)

    def test_reassignment_needs_fresh_owner(self):
        archived = {"wave": 1, "status": "covered", "agent_id": "h1", "reviewed_paths": ["src/app.js"],
                    "local_checks": [check()], "result_fingerprints": [], "unresolved": [],
                    "reassignment_reason": "critic: sibling route not read"}
        ok = unit(wave=2, attempts=[archived], status="in_progress", agent_id="h2")
        self.assertEqual(audit.validate_ledger([ok]), [])
        self.assertTrue(audit.validate_ledger([unit(wave=2, attempts=[archived], status="in_progress",
                                                    agent_id="h1")]))
        self.assertTrue(audit.validate_ledger([unit(wave=1, attempts=[archived], status="in_progress",
                                                    agent_id="h2")]))

    def test_sorted_unique_and_collision(self):
        a = unit()
        b = audit.new_unit({"surface": "DELETE", "boundary": "b", "subsystem": "s", "attack_class": "c",
                            "canonical_refs": {"surface": "src/app.js#DELETE /notes/:id", "boundary": "b",
                                               "subsystem": "s", "attack_class": "c"},
                            "starting_paths": ["src/app.js"]})
        first, second = sorted([a, b], key=lambda u: u["coverage_id"])
        self.assertEqual(audit.validate_ledger([first, second]), [])
        self.assertTrue(any("sorted" in e for e in audit.validate_ledger([second, first])))
        self.assertTrue(any("duplicate" in e for e in audit.validate_ledger([a, copy.deepcopy(a)])))
        tampered = copy.deepcopy(a)
        tampered["coverage_id"] = "x"
        self.assertTrue(any("expected canonical ID" in e for e in audit.validate_ledger([tampered])))


class CliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(str(self.tmp), ignore_errors=True)

    def run_py(self, script, *args, env=None):
        return subprocess.run([PY, "-I", str(HERE / script)] + [str(a) for a in args], stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, universal_newlines=True, env=env)

    def test_ledger_id_seed_merge_collision(self):
        r = self.run_py("audit-ledger.py", "id", "--surface", "a b", "--boundary", "b", "--subsystem", "s",
                        "--attack-class", "c")
        self.assertEqual(r.stdout.strip(), "a%20b::b::s::c")
        spec = {"surface": "S", "boundary": "B", "subsystem": "src", "attack_class": "A",
                "canonical_refs": {"surface": "s1", "boundary": "b", "subsystem": "src", "attack_class": "a"},
                "starting_paths": ["src/app.js"]}
        units, ledger = self.tmp / "u.json", self.tmp / "ledger.json"
        units.write_text(json.dumps([spec]))
        self.assertEqual(self.run_py("audit-ledger.py", "seed", units, "--out", ledger).returncode, 0)
        doc = json.loads(ledger.read_text())
        doc[0].update(status="covered", agent_id="h1", reviewed_paths=["src/app.js"], local_checks=[check()])
        ledger.write_text(json.dumps(doc))
        spec2 = dict(spec, surface="S0", canonical_refs=dict(spec["canonical_refs"], surface="s0"))
        units.write_text(json.dumps([spec, spec2]))
        r = self.run_py("audit-ledger.py", "seed", units, "--out", ledger, "--merge")
        self.assertEqual(r.returncode, 0, r.stderr)
        doc = json.loads(ledger.read_text())
        self.assertEqual([u["canonical_refs"]["surface"] for u in doc], ["s0", "s1"])
        self.assertEqual(doc[1]["status"], "covered")        # existing unit untouched
        units.write_text(json.dumps([dict(spec, surface="renamed")]))
        self.assertEqual(self.run_py("audit-ledger.py", "seed", units, "--out", ledger, "--merge").returncode, 1)

    def test_validate_cli_exit_codes(self):
        f = self.tmp / "findings.json"
        f.write_text(json.dumps([confirmed()]))
        self.assertEqual(self.run_py("validate-audit.py", "findings", f).returncode, 0)
        f.write_text(json.dumps([confirmed("b"), confirmed("a")]))   # unsorted
        self.assertEqual(self.run_py("validate-audit.py", "findings", f).returncode, 1)
        f.write_text("{not json")
        self.assertEqual(self.run_py("validate-audit.py", "findings", f).returncode, 2)
        f.write_bytes(b"[" + b" " * (5 * 1024 * 1024) + b"]")
        self.assertEqual(self.run_py("validate-audit.py", "findings", f).returncode, 2)

    @unittest.skipUnless(shutil.which("git"), "git required")
    def test_prepare_metadata_hints_and_since_scope(self):
        repo = self.tmp / "audit-demo"
        shutil.copytree(str(FIX / "audit-demo"), str(repo))
        g = ["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t"]
        subprocess.run(g + ["init", "-q"], check=True)
        subprocess.run(g + ["add", "-A"], check=True)
        subprocess.run(g + ["commit", "-qm", "init"], check=True)
        (repo / "src" / "extra.js").write_text("app.get('/x', h)\n")
        run = self.tmp / "security-run-20261103-090000"
        run.mkdir()
        env = dict(os.environ)
        env.pop("JOB_SECURITY_SCAN_AUDIT_EXEC", None)
        r = self.run_py("audit-prepare.py", "--repo", "audit-demo", "--path", repo, "--run-dir", run,
                        "--runs-root", self.tmp, "--profile", "quick", "--since", "HEAD", "--budget", "12", env=env)
        self.assertEqual(r.returncode, 0, r.stderr)
        audit_dir = run / "audit-demo" / "audit"
        meta = json.loads((audit_dir / "run-metadata.json").read_text())
        self.assertEqual((meta["profile"], meta["budget"], meta["execution_policy"], meta["run_status"]),
                         ("quick", 12, "source-only", "awaiting_agent"))
        self.assertEqual(meta["scope_paths"], ["src/extra.js"])
        self.assertTrue(meta["source_ref"]["dirty"])
        self.assertEqual(len(meta["source_ref"]["commit"]), 40)
        hints = json.loads((audit_dir / "recon-hints.json").read_text())
        self.assertEqual(hints["ecosystems"], ["node"])
        self.assertIn("http-routes", hints["groups"])
        self.assertTrue((audit_dir / "AGENT-TASK.md").is_file())
        r = self.run_py("audit-prepare.py", "--repo", "audit-demo", "--path", repo, "--run-dir", run,
                        "--runs-root", self.tmp, "--since", "--upload-pack=x")
        self.assertEqual(r.returncode, 2)
        # whole-repo hints see the planted surfaces
        run2 = self.tmp / "security-run-20261103-100000"
        run2.mkdir()
        (run / "audit-demo" / "audit" / "findings.json").write_text("[]")
        r = self.run_py("audit-prepare.py", "--repo", "audit-demo", "--path", repo, "--run-dir", run2,
                        "--runs-root", self.tmp, env=env)
        meta2 = json.loads((run2 / "audit-demo" / "audit" / "run-metadata.json").read_text())
        self.assertEqual(meta2["prior_runs"][0]["path"], str(run / "audit-demo" / "audit"))
        hints2 = json.loads((run2 / "audit-demo" / "audit" / "recon-hints.json").read_text())
        self.assertIn("ci-and-release", hints2["groups"])
        self.assertIn("file-and-process-sinks", hints2["groups"])
        for group in ("http-routes", "auth-and-sessions", "data-isolation"):
            self.assertIn(group, hints2["groups"])
        routes = set((h["file"], h["line"]) for h in hints2["groups"]["http-routes"]["hits"])
        self.assertIn(("src/app.js", 34), routes)   # GET /notes/:id branch


class ReportMergeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.dir = self.tmp / "api" / "audit"
        self.dir.mkdir(parents=True)

    def tearDown(self):
        shutil.rmtree(str(self.tmp), ignore_errors=True)

    def write(self, status="complete", ledger=True, findings=None):
        (self.dir / "run-metadata.json").write_text(json.dumps({"profile": "quick", "run_status": status,
                                                                 "execution_policy": "source-only"}))
        if ledger:
            u = unit(status="candidate", agent_id="h1", reviewed_paths=["src/app.js"], local_checks=[check()],
                     result_fingerprints=["notes-get-missing-owner-check"])
            u["hardening"] = ["add rate limiting to login"]
            (self.dir / "coverage-ledger.json").write_text(json.dumps([u]))
        if findings is not None:
            (self.dir / "findings.json").write_text(json.dumps(findings))

    def test_complete_audit_is_merged(self):
        self.write(findings=sorted([confirmed(), needs_validation(), rejected()], key=lambda r: r["fingerprint"]))
        merged, summary = audit_report.load(str(self.tmp), "api", "/w")
        self.assertEqual(len(merged), 1)
        f = merged[0]
        self.assertEqual((f["scanner"], f["severity"], f["file"], f["line"], f["verdict"]),
                         ("audit", "HIGH", "src/app.js", 38, "confirmed"))
        self.assertEqual(len(summary["needs_validation"]), 1)
        self.assertEqual(summary["rejected"], 1)
        self.assertEqual(summary["coverage"], {"candidate": 1})
        self.assertEqual(summary["hardening"], ["add rate limiting to login"])

    def test_not_merged_when_unfinished_invalid_or_without_ledger(self):
        for kwargs, reason in (({"status": "in_progress", "findings": [confirmed()]}, "run_status"),
                               ({"ledger": False, "findings": [confirmed()]}, "coverage-ledger.json missing"),
                               ({"findings": [confirmed("b"), confirmed("a")]}, "sorted"),
                               ({"status": "awaiting_agent"}, "not written yet")):
            for p in self.dir.iterdir():
                p.unlink()
            self.write(**kwargs)
            merged, summary = audit_report.load(str(self.tmp), "api", "/w")
            self.assertEqual(merged, [], kwargs)
            self.assertTrue(any(reason in e for e in summary["errors"]), (reason, summary["errors"]))

    def test_no_audit_folder(self):
        shutil.rmtree(str(self.dir))
        self.assertEqual(audit_report.load(str(self.tmp), "api", "/w"), ([], None))


def namespaces_available():
    try:
        return subprocess.run(["unshare", "-r", "-n", "-m", "--fork", "--", "true"],
                              capture_output=True, timeout=30).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


class SandboxAndPromotionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.agent = self.tmp / "audit" / "agents" / "v1"
        self.scratch = self.agent / "scratch"
        self.scratch.mkdir(parents=True)

    def tearDown(self):
        shutil.rmtree(str(self.tmp), ignore_errors=True)

    def sandbox(self, *args, exec_on=True):
        env = dict(os.environ)
        env.pop("JOB_SECURITY_SCAN_AUDIT_EXEC", None)
        if exec_on:
            env["JOB_SECURITY_SCAN_AUDIT_EXEC"] = "1"
        return subprocess.run([PY, "-I", str(HERE / "audit-sandbox.py"), "--scratch", str(self.scratch)]
                              + list(args), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              universal_newlines=True, env=env)

    def test_disabled_by_default(self):
        r = self.sandbox("--", "true", exec_on=False)
        self.assertEqual(r.returncode, 97)
        self.assertIn("JOB_SECURITY_SCAN_AUDIT_EXEC", r.stderr)

    def test_argument_guards(self):
        self.assertEqual(self.sandbox("--env", "NPM_TOKEN=x", "--", "true").returncode, 98)
        self.assertEqual(self.sandbox("--env", "LD_PRELOAD=x", "--", "true").returncode, 98)
        bad = self.tmp / "elsewhere"
        bad.mkdir()
        r = subprocess.run([PY, "-I", str(HERE / "audit-sandbox.py"), "--scratch", str(bad), "--", "true"],
                           env=dict(os.environ, JOB_SECURITY_SCAN_AUDIT_EXEC="1"), capture_output=True)
        self.assertEqual(r.returncode, 98)

    @unittest.skipUnless(sys.platform.startswith("linux") and namespaces_available(), "needs Linux namespaces")
    def test_self_test_and_controls(self):
        r = self.sandbox("--self-test")
        self.assertEqual(r.returncode, 0, r.stderr)
        result = json.loads(r.stdout)
        self.assertTrue(result["sandbox_ok"])
        self.assertFalse(result["network"])
        r = self.sandbox("--wall-seconds", "2", "--", "sh", "-c", "sleep 10")
        self.assertEqual(r.returncode, 124)
        record = self.tmp / "record.json"
        r = self.sandbox("--record", str(record), "--env", "MODE=test", "--", "sh", "-c",
                         'echo "$MODE" > result.txt; touch /escape 2>/dev/null && exit 3; exit 0')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual((self.scratch / "result.txt").read_text().strip(), "test")
        self.assertIn("MODE", json.loads(record.read_text())["env_names"])
        (self.scratch / "harness.sh").write_text("cat harness.sh > copy.txt\n")
        self.assertEqual(self.sandbox("--", "sh", "harness.sh").returncode, 0)
        self.assertTrue((self.scratch / "copy.txt").is_file())         # pre-written harness visible, output kept
        r = self.sandbox("--disk-mb", "2", "--file-size-mb", "64", "--", "sh", "-c",
                         "head -c 5000000 /dev/zero > fill.bin")
        self.assertNotEqual(r.returncode, 0)                            # cumulative disk quota enforced
        (self.scratch / "fill.bin").unlink()
        (self.scratch / "big.bin").write_bytes(b"x" * 3 * 1024 * 1024)
        self.assertEqual(self.sandbox("--disk-mb", "2", "--", "true").returncode, 97)

    def promote(self, *files):
        return subprocess.run([PY, "-I", str(HERE / "audit-promote.py"), "--agent-dir", str(self.agent)]
                              + [a for f in files for a in ("--file", f)] + ["--max-file-bytes", "64"],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)

    def test_promotion(self):
        (self.scratch / "d").mkdir()
        (self.scratch / "d" / "ok.txt").write_text("status 200\n")
        (self.scratch / "big.txt").write_text("x" * 100)
        os.symlink("/etc/hostname", str(self.scratch / "link"))
        (self.scratch / "h").write_text("a")
        os.link(str(self.scratch / "h"), str(self.scratch / "h2"))
        r = self.promote("d/ok.txt", "big.txt", "link", "h", "../escape", "missing")
        self.assertEqual(r.returncode, 1)
        self.assertIn("agents/v1/artifacts/d/ok.txt", r.stdout)
        self.assertEqual(r.stdout.count("REFUSED"), 5, r.stdout)
        self.assertEqual((self.agent / "artifacts" / "d" / "ok.txt").read_text(), "status 200\n")
        self.assertIn("destination already exists", self.promote("d/ok.txt").stdout)
        os.symlink(str(self.tmp), str(self.tmp / "audit" / "agents" / "v2"))
        r = subprocess.run([PY, "-I", str(HERE / "audit-promote.py"), "--agent-dir",
                            str(self.tmp / "audit" / "agents" / "v2"), "--file", "x"], capture_output=True)
        self.assertEqual(r.returncode, 2)


if __name__ == "__main__":
    unittest.main()
