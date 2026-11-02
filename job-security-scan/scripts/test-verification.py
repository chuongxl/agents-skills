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


META = {"team": "t", "org": "o", "config": "c", "run_dir": "/w/security-run-20261102-220000",
        "scanners": ["semgrep", "osv"], "repos": ["api"], "skipped": [], "generated_at": "x",
        "profile": "standard", "since": None, "coverage": {"api": ["semgrep", "osv"]}}
OSV_ROW = dict(scanner="osv", type="vulnerability", file="yarn.lock", line=3, code="x", package="lodash",
               installed_version="4.17.15", rule_id="GHSA-x", severity="MEDIUM")
CONFIRMED = {"verdict": "confirmed", "verified_severity": "HIGH",
             "verdict_detail": {"evidence": "id comes from req.query", "likelihood": "high", "impact": "high"}}


def build(findings, previous=None, **meta):
    import report_model
    m = dict(META)
    m.update(meta)
    return report_model.build_document(findings, m, previous=previous)


class ChangesTests(unittest.TestCase):
    def test_first_run_everything_new(self):
        doc = build([finding()])
        self.assertEqual(doc["findings"][0]["change"], "new")
        self.assertIsNone(doc["run"]["previous_run"])

    def test_new_unchanged_fixed(self):
        prev = build([finding(), finding(**OSV_ROW)], run_dir="/w/security-run-1")
        cur = build([finding(line=50), finding(code="other()", rule_id="xss")], previous=prev)
        by = dict((f["rule_id"], f["change"]) for f in cur["findings"])
        self.assertEqual(by, {"sqli": "unchanged", "xss": "new"})
        self.assertEqual([f["rule_id"] for f in cur["fixed"]], ["GHSA-x"])
        self.assertEqual(cur["run"]["previous_run"], "/w/security-run-1")

    def test_edited_code_is_new(self):
        prev = build([finding()])
        cur = build([finding(code="db.query('SELECT ' + id + limit)")], previous=prev)
        self.assertEqual(cur["findings"][0]["change"], "new")

    def test_scanner_not_run_now_is_not_fixed(self):
        prev = build([finding(), finding(**OSV_ROW)])
        cur = build([finding()], previous=prev, scanners=["semgrep"], coverage={"api": ["semgrep"]})
        self.assertEqual(cur["fixed"], [])

    def test_repo_not_scanned_now_is_not_fixed(self):
        prev = build([finding(), finding(repo="web")], repos=["api", "web"],
                     coverage={"api": ["semgrep"], "web": ["semgrep"]})
        cur = build([finding()], previous=prev, coverage={"api": ["semgrep"]})
        self.assertEqual(cur["fixed"], [])

    def test_partial_runs_never_mark_fixed(self):
        prev = build([finding(), finding(**OSV_ROW)])
        self.assertEqual(build([finding()], previous=prev, since="main")["fixed"], [])
        self.assertEqual(build([finding()], previous=prev, partial=True)["fixed"], [])
        partial_prev = build([finding(), finding(**OSV_ROW)], since="main")
        self.assertEqual(build([finding()], previous=partial_prev)["fixed"], [])

    def test_verdict_carried_to_unchanged_only(self):
        import report_schema
        prev = build([dict(finding(), **CONFIRMED)])
        cur = build([finding(line=99), finding(code="changed()")], previous=prev)
        moved, edited = cur["findings"]
        self.assertEqual((moved["verdict"], moved["verified_severity"], moved["carried"]), ("confirmed", "HIGH", True))
        self.assertIsNone(edited["verdict"])
        self.assertFalse(edited["carried"])
        self.assertEqual(report_schema.validate(cur), [])

    def test_v1_previous_is_no_previous(self):
        cur = build([finding()], previous={"schema_version": 1, "findings": [finding()]})
        self.assertEqual(cur["findings"][0]["change"], "new")
        self.assertIsNone(cur["run"]["previous_run"])

    def test_find_previous_run(self):
        import report_model
        root = Path(tempfile.mkdtemp())
        try:
            def mk(name, doc):
                d = root / name
                d.mkdir()
                if doc is not None:
                    (d / "security-report.json").write_text(json.dumps(doc) if isinstance(doc, dict) else doc)
                return d
            mk("security-run-20261101-090000", build([finding()]))
            mk("security-run-20261101-100000", {"schema_version": 1, "findings": []})
            mk("security-run-20261101-110000", "{not json")
            mk("security-run-20261101-120000", None)
            mk("not-a-run", build([finding()]))
            cur = mk("security-run-20261102-080000", None)
            later = mk("security-run-20261103-080000", build([finding()]))
            doc, path = report_model.find_previous(cur)
            self.assertEqual(path.name, "security-run-20261101-090000")
            self.assertEqual(doc["schema_version"], 2)
            self.assertTrue(later.exists())
            self.assertEqual(report_model.find_previous(root / "security-run-20261101-090000"), (None, None))
        finally:
            shutil.rmtree(str(root), ignore_errors=True)


def write_results(base, semgrep_rows, repo="api"):
    """A run folder with semgrep output for `repo` (base/repo/semgrep.json)."""
    d = base / repo
    d.mkdir(parents=True, exist_ok=True)
    (d / "semgrep.json").write_text(json.dumps({"results": [
        {"check_id": rid, "path": path, "start": {"line": line}, "extra": {"severity": "ERROR", "message": rid}}
        for rid, path, line in semgrep_rows]}))


class GenerateChangesTests(TempDirCase):
    def generate(self, run, *extra):
        cfg = self.tmp / "repository.md"
        if not cfg.exists():
            cfg.write_text("---\nteam: acme\norg: acme-org\nrepos:\n  - name: api\n    active: true\n---\n")
        return run_proc(GENERATE, "--results-dir", run, "--config", cfg, "--out-dir", run,
                        "--repos-root", self.tmp / "repos", "--home", self.tmp / "home", *extra)

    def test_second_run_reports_changes(self):
        self.put("repos/api/src/db.js", "const q = 'SELECT ' + id;\nconst r = 'DELETE ' + id;\n")
        first = self.tmp / "ws" / "security-run-20261102-090000"
        write_results(first, [("sqli", "src/db.js", 1), ("sqli-delete", "src/db.js", 2)])
        r = self.generate(first)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.put("repos/api/src/db.js", "// moved\nconst q = 'SELECT ' + id;\nconst x = eval(input);\n")
        second = self.tmp / "ws" / "security-run-20261102-100000"
        write_results(second, [("sqli", "src/db.js", 2), ("eval", "src/db.js", 3)])
        r = self.generate(second)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        doc = json.loads((second / "security-report.json").read_text())
        self.assertEqual(dict((f["rule_id"], f["change"]) for f in doc["findings"]),
                         {"sqli": "unchanged", "eval": "new"})
        self.assertEqual([f["rule_id"] for f in doc["fixed"]], ["sqli-delete"])
        self.assertEqual(doc["run"]["previous_run"], str(first.resolve()))
        self.assertEqual(run_proc(VALIDATE, second / "security-report.json").returncode, 0)
        md = (second / "security-report.md").read_text()
        self.assertIn("## 🔁 Changes since last run", md)
        self.assertIn("sqli-delete", md.split("## 🔁 Changes since last run")[1].split("\n## ")[0])
        page = (second / "security-report.html").read_text()
        self.assertIn('class="badge-new"', page)
        self.assertEqual(page.count('class="badge-new"'), 1)

    def test_absolute_scanner_paths_become_repo_relative(self):
        self.put("repos/api/src/db.js", "const q = 'SELECT ' + id;\n")
        run_dir = self.tmp / "ws" / "security-run-20261102-090000"
        write_results(run_dir, [("sqli", str(self.tmp / "repos" / "api" / "src" / "db.js"), 1)])
        self.assertEqual(self.generate(run_dir).returncode, 0)
        f = json.loads((run_dir / "security-report.json").read_text())["findings"][0]
        self.assertEqual((f["file"], f["line"], f["code"]), ("src/db.js", 1, "const q = 'SELECT ' + id;"))
        page = (run_dir / "security-report.html").read_text()
        self.assertIn("vscode://file%s" % (self.tmp / "repos" / "api" / "src" / "db.js"), page)

    def test_previous_none_disables_comparison(self):
        first = self.tmp / "ws" / "security-run-20261102-090000"
        write_results(first, [("sqli", "src/db.js", 1)])
        self.generate(first)
        second = self.tmp / "ws" / "security-run-20261102-100000"
        write_results(second, [("sqli", "src/db.js", 1)])
        self.assertEqual(self.generate(second, "--previous", "none").returncode, 0)
        doc = json.loads((second / "security-report.json").read_text())
        self.assertEqual(doc["findings"][0]["change"], "new")


def run_proc(*args, **kw):
    return run(*args, **kw)


STUB = '''#!/usr/bin/env bash
echo "%(name)s $*" >> "%(log)s"
out=""; prev=""
for a in "$@"; do
  { [ "$prev" = "--report-path" ] || [ "$prev" = "--output" ]; } && out="$a"
  prev="$a"
done
if [ -n "$out" ]; then
  if [ "%(name)s" = gitleaks ] && [ -n "${GITLEAKS_FIXTURE:-}" ]; then cp "$GITLEAKS_FIXTURE" "$out"; exit 1
  elif [ "%(name)s" = gitleaks ]; then echo "[]" > "$out"
  else echo "{}" > "$out"; fi
fi
exit 0
'''


def git(cwd, *args):
    env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t",
               GIT_COMMITTER_EMAIL="t@t", GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")
    return subprocess.run(["git"] + list(args), cwd=str(cwd), env=env, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, universal_newlines=True, check=True).stdout.strip()


@unittest.skipUnless(shutil.which("bash") and shutil.which("git"), "bash and git required")
class ProfileTests(TempDirCase):
    def setUp(self):
        super(ProfileTests, self).setUp()
        self.ws = self.tmp / "ws"
        self.repos = self.tmp / "repos"
        (self.repos / "api").mkdir(parents=True)
        self.ws.mkdir()
        self.bin = self.tmp / "bin"
        self.bin.mkdir()
        self.log = self.tmp / "calls.log"
        for name in ("gitleaks", "trivy", "semgrep", "osv-scanner", "trufflehog", "hadolint"):
            p = self.bin / name
            p.write_text(STUB % {"name": name, "log": self.log})
            p.chmod(0o755)
        self.cfg = self.put("ws/repository.md", '---\nteam: t\norg: o\nmonorepo-root: "%s"\nci-runner: x\n'
                            'fail-on-severity: HIGH\nrepos:\n  - name: api\n    active: true\n'
                            '    has-dockerfile: false\n---\n' % self.repos)

    def scan(self, *args, **env):
        e = dict(os.environ, PATH=str(self.bin) + os.pathsep + os.environ["PATH"], SECURITY_RUN_ROOT=str(self.ws),
                 XDG_CACHE_HOME=str(self.tmp / "xdg"), HOME=str(self.tmp / "home"), NPM_CONFIG_PREFIX="",
                 ADVISORY_OFFLINE="1")
        e.pop("JOB_SECURITY_SCAN_CACHE", None)
        e.update(env)
        (self.tmp / "home").mkdir(exist_ok=True)
        r = subprocess.run(["bash", str(RUN_SCAN), "--config", str(self.cfg)] + [str(a) for a in args],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True,
                           cwd=str(self.ws), env=e)
        runs = sorted(self.ws.glob("security-run-*"))
        return r, runs[-1] if runs else None

    def calls(self):
        return self.log.read_text() if self.log.exists() else ""

    def report(self, run_dir):
        return json.loads((run_dir / "security-report.json").read_text())

    def test_quick_profile(self):
        r, run_dir = self.scan("--profile", "quick")
        out = r.stdout + r.stderr
        self.assertIn("gitleaks detect", self.calls())
        self.assertIn("--no-git", self.calls())
        self.assertNotIn("trivy", self.calls())
        self.assertIn("[osv]", out)
        self.assertIn("[shai-hulud]", out)
        self.assertNotIn("[semgrep]", out)
        doc = self.report(run_dir)
        self.assertEqual((doc["run"]["profile"], doc["verification"]["queued"]), ("quick", 0))
        self.assertEqual(run_proc(VALIDATE, run_dir / "security-report.json").returncode, 0)

    def test_standard_is_default(self):
        r, run_dir = self.scan()
        self.assertIn("--log-opts --all", self.calls())
        self.assertIn("--severity MEDIUM,HIGH,CRITICAL", self.calls())
        self.assertIn("[semgrep]", r.stdout)
        self.assertEqual(self.report(run_dir)["run"]["profile"], "standard")

    def test_deep_adds_trivy_low(self):
        r, run_dir = self.scan("--profile", "deep")
        self.assertIn("--severity LOW,MEDIUM,HIGH,CRITICAL", self.calls())
        self.assertEqual(self.report(run_dir)["run"]["profile"], "deep")

    def test_scanner_overrides_profile(self):
        r, run_dir = self.scan("--profile", "quick", "--scanner", "trivy")
        self.assertIn("trivy fs", self.calls())
        self.assertNotIn("gitleaks", self.calls())

    def test_bad_profile_and_bad_ref_make_no_folder(self):
        for args in (("--profile", "fast"), ("--since", "--upload-pack=x"), ("--since", "a b"), ("--since",)):
            r, run_dir = self.scan(*args)
            self.assertEqual(r.returncode, 1, (args, r.stdout))
            self.assertIsNone(run_dir, args)

    def leaks(self, *files):
        rows = [{"File": f, "StartLine": 1, "RuleID": "generic-api-key", "Description": "key", "Commit": "abc"}
                for f in files]
        return str(self.put("leaks.json", json.dumps(rows)))

    def test_since_keeps_changed_files_only(self):
        api = self.repos / "api"
        (api / "old.js").write_text("const k = 1;\n")
        git(api, "init", "-q")
        git(api, "add", ".")
        git(api, "commit", "-qm", "a")
        base = git(api, "rev-parse", "HEAD")
        (api / "new.js").write_text("const k = 2;\n")
        git(api, "add", ".")
        git(api, "commit", "-qm", "b")
        (api / "wip.js").write_text("const k = 3;\n")   # untracked working-tree change counts too
        r, run_dir = self.scan("--profile", "quick", "--since", base,
                               GITLEAKS_FIXTURE=self.leaks("old.js", "new.js", "wip.js"))
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        doc = self.report(run_dir)
        self.assertEqual(sorted(f["file"] for f in doc["findings"]), ["new.js", "wip.js"])
        self.assertEqual((doc["run"]["since"], doc["run"]["partial"], doc["fixed"]), (base, True, []))
        self.assertIn("partial", (run_dir / "security-report.md").read_text())
        changed = json.loads((run_dir / "changed-files.json").read_text())
        self.assertEqual(sorted(changed["api"]), ["new.js", "wip.js"])

    def test_since_unknown_ref_or_not_git_is_full_scope(self):
        (self.repos / "api" / "old.js").write_text("x\n")
        r, run_dir = self.scan("--profile", "quick", "--since", "main", GITLEAKS_FIXTURE=self.leaks("old.js"))
        self.assertIn("full scope", r.stdout)
        self.assertEqual([f["file"] for f in self.report(run_dir)["findings"]], ["old.js"])
        git(self.repos / "api", "init", "-q")
        r, run_dir = self.scan("--profile", "quick", "--since", "nope", GITLEAKS_FIXTURE=self.leaks("old.js"))
        self.assertIn("full scope", r.stdout)
        self.assertEqual(len(self.report(run_dir)["findings"]), 1)

    def test_quick_after_standard_marks_no_secret_fixed(self):
        """Gitleaks history (standard) vs working tree (quick) are different coverage: nothing is 'fixed'."""
        self.scan(GITLEAKS_FIXTURE=self.leaks("old.js"))
        r, run_dir = self.scan("--profile", "quick")
        doc = self.report(run_dir)
        self.assertIsNotNone(doc["run"]["previous_run"])
        self.assertEqual(doc["fixed"], [])
        # same profile twice: the secret really is gone, so it is fixed
        self.scan("--profile", "quick", GITLEAKS_FIXTURE=self.leaks("old.js"))
        r, run_dir = self.scan("--profile", "quick")
        self.assertEqual([f["file"] for f in self.report(run_dir)["fixed"]], ["old.js"])


DB_JS = "\n".join(["// line %d" % i for i in range(1, 20)] +
                  ["const q = 'SELECT ' + req.query.id;",          # line 20
                   "const token = '%s';" % SECRET] +                # line 21: must come out redacted
                  ["// tail %d" % i for i in range(22, 60)]) + "\n"


class TriageTests(TempDirCase):
    """triage.py queue / apply against a real generated run folder."""

    def setUp(self):
        super(TriageTests, self).setUp()
        self.put("repos/api/src/db.js", DB_JS)
        self.put("repos/api/src/ui.js", "el.innerHTML = name;\n")
        self.put("repos/api/.env", "API_KEY=%s\n" % SECRET)
        self.put("repos/api/.env.example", "x = eval(input)\n")
        os.symlink("/etc/hostname", str(self.tmp / "repos" / "api" / "link.js"))
        self.cfg = self.put("repository.md", "---\nteam: acme\norg: acme-org\nrepos:\n  - name: api\n"
                            "    active: true\n---\n")
        self.ws = self.tmp / "ws"

    def make_run(self, name="security-run-20261102-090000", profile="standard"):
        run_dir = self.ws / name
        d = run_dir / "api"
        d.mkdir(parents=True)
        (d / "semgrep.json").write_text(json.dumps({"results": [
            {"check_id": "sqli", "path": "src/db.js", "start": {"line": 20},
             "extra": {"severity": "ERROR", "message": "SQL injection"}},
            {"check_id": "xss", "path": "src/ui.js", "start": {"line": 1},
             "extra": {"severity": "WARNING", "message": "XSS"}},
            {"check_id": "eval", "path": ".env.example", "start": {"line": 1},
             "extra": {"severity": "ERROR", "message": "eval"}},
            {"check_id": "link", "path": "link.js", "start": {"line": 1},
             "extra": {"severity": "ERROR", "message": "symlink"}}]}))
        (d / "gitleaks.json").write_text(json.dumps([{"File": ".env", "StartLine": 1, "RuleID": "github-pat",
                                                      "Description": "GitHub token", "Commit": "abc"}]))
        r = run_proc(GENERATE, "--results-dir", run_dir, "--config", self.cfg, "--out-dir", run_dir,
                     "--repos-root", self.tmp / "repos", "--home", self.tmp / "home", "--profile", profile)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return run_dir

    def doc(self, run_dir):
        return json.loads((run_dir / "security-report.json").read_text())

    def queue(self, run_dir):
        r = run_proc(TRIAGE, "queue", run_dir)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return json.loads((run_dir / "triage" / "queue.json").read_text())

    def fp(self, run_dir, rule):
        return [f["fingerprint"] for f in self.doc(run_dir)["findings"] if f["rule_id"] == rule][0]

    def apply(self, run_dir, verdicts):
        p = self.put("verdicts-%d.json" % len(list(self.tmp.glob("verdicts-*"))),
                     verdicts if isinstance(verdicts, str) else json.dumps(verdicts))
        return run_proc(TRIAGE, "apply", run_dir, p)

    def test_queue_by_profile_and_context(self):
        run_dir = self.make_run()
        q = self.queue(run_dir)
        by = dict((i["rule_id"], i) for i in q["items"])
        self.assertEqual(sorted(by), ["eval", "github-pat", "link", "sqli"])      # HIGH+CRITICAL, not xss
        ctx = by["sqli"]["context"]
        self.assertEqual((ctx["start_line"], ctx["end_line"]), (5, 35))
        text = "\n".join(ctx["lines"])
        self.assertIn(">   20 | const q = 'SELECT ' + req.query.id;", text)
        self.assertNotIn(SECRET, json.dumps(q))
        self.assertIn("gh_***", text)

    def test_queue_never_carries_secret_or_credential_file_content(self):
        run_dir = self.make_run()
        by = dict((i["rule_id"], i) for i in self.queue(run_dir)["items"])
        self.assertEqual((by["github-pat"]["code"], by["github-pat"]["context"]), ("", None))
        self.assertIsNone(by["eval"]["context"])      # .env* files are never opened for context
        self.assertIsNone(by["link"]["context"])      # symlinks are not followed
        self.assertNotIn(SECRET, (run_dir / "triage" / "queue.json").read_text())

    def test_quick_profile_queues_nothing_deep_adds_medium(self):
        self.assertEqual(self.queue(self.make_run(profile="quick"))["items"], [])
        q = self.queue(self.make_run(name="security-run-20261102-100000", profile="deep"))
        self.assertIn("xss", [i["rule_id"] for i in q["items"]])

    def good_verdicts(self, run_dir):
        return {"verdicts": [
            {"fingerprint": self.fp(run_dir, "sqli"), "verdict": "confirmed", "severity": "MEDIUM",
             "likelihood": "medium", "impact": "medium",
             "evidence": "id flows from req.query into the SQL string at src/db.js:20 (%s)" % SECRET},
            {"fingerprint": self.fp(run_dir, "eval"), "verdict": "rejected",
             "reason": "example file, never loaded at runtime"},
            {"fingerprint": self.fp(run_dir, "link"), "verdict": "needs_validation",
             "blocker": "symlink target outside the repo", "validation_plan": "check the deployed file"}]}

    def test_apply_merges_and_regenerates(self):
        run_dir = self.make_run()
        before = self.doc(run_dir)["counts"]
        r = self.apply(run_dir, self.good_verdicts(run_dir))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        doc = self.doc(run_dir)
        self.assertEqual(run_proc(VALIDATE, run_dir / "security-report.json").returncode, 0)
        # sqli HIGH -> MEDIUM, eval dismissed (out of counts), link needs validation (keeps the tool's HIGH)
        self.assertEqual(doc["counts"]["HIGH"], before["HIGH"] - 2)
        self.assertEqual(doc["counts"]["MEDIUM"], before["MEDIUM"] + 1)
        by = dict((f["rule_id"], f) for f in doc["findings"])
        self.assertEqual((by["sqli"]["verdict"], by["sqli"]["verified_severity"]), ("confirmed", "MEDIUM"))
        self.assertEqual(by["eval"]["verdict_detail"]["reason"], "example file, never loaded at runtime")
        self.assertEqual(doc["verification"]["pending"], 1)            # github-pat still waits
        md = (run_dir / "security-report.md").read_text()
        self.assertIn("## 🚫 Dismissed (with reason)", md)
        self.assertIn("✅ confirmed as MEDIUM — tool said HIGH", md)
        needs = (run_dir / "NEEDS-VALIDATION.md").read_text()
        self.assertIn("symlink target outside the repo", needs)
        self.assertIn("check the deployed file", needs)
        for name in ("security-report.md", "security-report.json", "security-report.html", "NEEDS-VALIDATION.md"):
            self.assertNotIn(SECRET, (run_dir / name).read_text(), name)
        self.assertIn("verdict confirmed", (run_dir / "security-report.html").read_text())

    def test_apply_is_idempotent(self):
        run_dir = self.make_run()
        v = self.good_verdicts(run_dir)
        self.assertEqual(self.apply(run_dir, v).returncode, 0)
        first = (run_dir / "security-report.json").read_text()
        self.assertEqual(self.apply(run_dir, v).returncode, 0)
        self.assertEqual((run_dir / "security-report.json").read_text(), first)

    def test_apply_rejects_bad_input_and_changes_nothing(self):
        run_dir = self.make_run()
        fp = self.fp(run_dir, "sqli")
        original = (run_dir / "security-report.json").read_text()
        ok = {"fingerprint": fp, "verdict": "rejected", "reason": "r"}
        bad_inputs = [
            "Here are my verdicts:\n" + json.dumps({"verdicts": [ok]}),       # prose-wrapped
            json.dumps("nope"),
            json.dumps({"verdicts": [dict(ok, fingerprint="0" * 16)]}),        # unknown fingerprint
            json.dumps({"verdicts": [ok, ok]}),                                # duplicate
            json.dumps({"verdicts": [dict(ok, extra="x")]}),                   # unknown key
            json.dumps({"verdicts": [{"fingerprint": fp, "verdict": "rejected"}]}),
            json.dumps({"verdicts": [{"fingerprint": fp, "verdict": "confirmed", "severity": "CRITICAL",
                                      "likelihood": "high", "impact": "low", "evidence": "e"}]}),
            json.dumps({"verdicts": [{"fingerprint": fp, "verdict": "needs_validation", "blocker": "b"}]}),
            json.dumps({"verdicts": [ok, {"fingerprint": self.fp(run_dir, "eval"), "verdict": "maybe"}]}),
            json.dumps({"verdicts": [dict(ok, reason="x" * 5000)]}),
        ]
        for text in bad_inputs:
            r = self.apply(run_dir, text)
            self.assertEqual(r.returncode, 1, text[:80])
            self.assertEqual((run_dir / "security-report.json").read_text(), original, text[:80])
        self.assertFalse((run_dir / "NEEDS-VALIDATION.md").exists())

    def test_carried_verdicts_are_not_queued_again(self):
        first = self.make_run()
        self.assertEqual(self.apply(first, self.good_verdicts(first)).returncode, 0)
        second = self.make_run(name="security-run-20261102-100000")
        doc = self.doc(second)
        by = dict((f["rule_id"], f) for f in doc["findings"])
        self.assertTrue(by["sqli"]["carried"])
        self.assertEqual(sorted(i["rule_id"] for i in self.queue(second)["items"]), ["github-pat"])


CHANGED = SKILL_DIR / "scripts" / "changed-files.py"


@unittest.skipUnless(shutil.which("git"), "git required")
class ChangedFilesTests(TempDirCase):
    def test_repo_config_cannot_run_commands(self):
        repo = self.tmp / "evil"
        repo.mkdir()
        git(repo, "init", "-q")
        (repo / "a.js").write_text("x\n")
        git(repo, "add", ".")
        git(repo, "commit", "-qm", "a")
        marker = self.tmp / "pwned"
        hook = self.tmp / "hook.sh"
        hook.write_text("#!/bin/sh\ntouch '%s'\n" % marker)
        hook.chmod(0o755)
        with open(str(repo / ".git" / "config"), "a") as fh:
            fh.write("[core]\n\tfsmonitor = %s\n[diff]\n\texternal = %s\n" % (hook, hook))
        (repo / "b.js").write_text("y\n")
        out = self.tmp / "changed.json"
        r = run_proc(CHANGED, "--since", "HEAD", "--repos-root", self.tmp, "--out", out, "evil")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(json.loads(out.read_text()), {"evil": ["b.js"]})
        self.assertFalse(marker.exists(), "repo-controlled command ran")

    def test_invalid_refs_refused(self):
        for ref in ("--output=x", "a b", "", "x" * 300, "a;b"):
            r = run_proc(CHANGED, "--since=" + ref, "--repos-root", self.tmp, "--out", self.tmp / "o.json", "r")
            self.assertEqual(r.returncode, 1, ref)


class ScopeTests(unittest.TestCase):
    def test_filter_rules(self):
        import report_scope
        rows = [finding(file="src/a.js"), finding(file="src/b.js"), finding(file=".env", type="secret"),
                finding(scanner="osv", type="vulnerability", file="", package="lodash", installed_version="1"),
                finding(file="", rule_id="nofile"), finding(repo="this machine", file="/x"),
                finding(repo="web", file="src/a.js"), finding(repo="lib", file="z.js")]
        kept = report_scope.filter_changed(rows, {"api": {"src/a.js", ".env"}, "web": set(), "lib": None})
        got = [(f["repo"], f["file"], f["rule_id"]) for f in kept]
        self.assertEqual(got, [("api", "src/a.js", "sqli"), ("api", ".env", "sqli"), ("api", "", "nofile"),
                               ("this machine", "/x", "sqli"), ("lib", "z.js", "sqli")])
        dep = report_scope.filter_changed(rows[3:4], {"api": {"sub/package-lock.json"}})
        self.assertEqual(len(dep), 1)


if __name__ == "__main__":
    unittest.main()
