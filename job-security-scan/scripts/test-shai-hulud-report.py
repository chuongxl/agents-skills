#!/usr/bin/env python3
"""Tests for the Shai-Hulud section of the reports: what the scanner records it checked, and the per-target
verdict table (affected / suspicious / clean / error / not run) in security-report.{md,json,html}.

Run: python3 -I scripts/test-shai-hulud-report.py [TestClass ...] [-v]
No network, no scanner binaries. Stdlib only; Python 3.8+.
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

FIX = SKILL_DIR / "tests" / "fixtures" / "shai-hulud"
CLI = SKILL_DIR / "scripts" / "shai-hulud-scan.py"
GENERATE = SKILL_DIR / "scripts" / "generate-report.py"
VALIDATE = SKILL_DIR / "scripts" / "validate-report.py"
NPM_TOKEN = "npm_" + "SHAIREPORTTESTTOKEN0000000000000000"


def run(*args, **kw):
    return subprocess.run([sys.executable, "-I"] + [str(a) for a in args], stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, universal_newlines=True, **kw)


class TempDirCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(str(self.tmp), ignore_errors=True)

    def scan(self, *args, out=None, env=None):
        out = out or self.tmp / "out.json"
        r = run(CLI, *args, "--output", out, "--format", "json", env=env)
        self.assertIn(r.returncode, (0, 1, 2), r.stderr)
        return json.loads(Path(out).read_text())


class CheckedTests(TempDirCase):
    """The scanner says what it looked at, so a CLEAN verdict can be checked."""

    def test_repo_mode_records_what_it_checked(self):
        doc = self.scan("--repo", FIX / "infected-lockfile")
        c = doc["checked"]
        self.assertEqual(doc["verdict"], "affected")
        self.assertTrue(c["ioc_version"])
        self.assertGreater(c["ioc_packages"], 0)
        self.assertEqual(c["dependency_files"], ["package-lock.json"])
        self.assertGreaterEqual(c["packages"], 2)
        self.assertEqual(c["manifests"], 1)
        self.assertIn("install_hooks", c)
        self.assertIn("workflows", c)

    def test_installed_packages_and_hooks_counted(self):
        c = self.scan("--repo", FIX / "suspicious-hook")["checked"]
        self.assertGreaterEqual(c["installed_packages"], 1)
        self.assertGreaterEqual(c["install_hooks"], 1)
        self.assertGreaterEqual(c["manifests"], 2)

    def test_empty_repo_checked_nothing(self):
        (self.tmp / "empty").mkdir()
        doc = self.scan("--repo", self.tmp / "empty")
        self.assertEqual(doc["verdict"], "clean")
        c = doc["checked"]
        self.assertEqual((c["packages"], c["dependency_files"], c["manifests"]), (0, [], 0))

    def test_host_mode_records_what_it_checked(self):
        home = self.tmp / "home"
        proj = home / "code" / "app"
        proj.mkdir(parents=True)
        shutil.copy(str(FIX / "infected-lockfile" / "package-lock.json"), str(proj / "package-lock.json"))
        shutil.copy(str(FIX / "infected-lockfile" / "package.json"), str(proj / "package.json"))
        (home / ".npmrc").write_text("//registry.npmjs.org/:_authToken=%s\n" % NPM_TOKEN)
        env = dict(os.environ, HOME=str(home), npm_config_cache=str(home / ".npm"))
        doc = self.scan("--host", "--root", home, env=env)
        c = doc["checked"]
        self.assertEqual(doc["mode"], "host")
        self.assertEqual(c["projects"], 1)
        self.assertGreaterEqual(c["packages"], 2)
        self.assertEqual(c["credential_stores"], 1)
        for key in ("global_packages", "python_packages", "npm_cache_entries"):
            self.assertIn(key, c)
        self.assertNotIn(NPM_TOKEN, json.dumps(doc))

    def test_checked_holds_only_counts_and_relative_paths(self):
        c = self.scan("--repo", FIX / "clean")["checked"]
        for k, v in c.items():
            self.assertTrue(isinstance(v, (int, str, list)), k)
            if isinstance(v, list):
                self.assertTrue(all(isinstance(p, str) and not os.path.isabs(p) for p in v), k)


class ReportSectionTests(TempDirCase):
    """generate-report.py turns each target's raw output into a row of the Shai-Hulud section."""

    def setUp(self):
        super(ReportSectionTests, self).setUp()
        self.run_dir = self.tmp / "ws" / "security-run-20261103-090000"
        self.repos = self.tmp / "repos"
        for name, fixture in (("infected", "infected-lockfile"), ("hooky", "suspicious-hook"), ("clean", "clean")):
            shutil.copytree(str(FIX / fixture), str(self.repos / name))
        self.cfg = self.tmp / "repository.md"
        self.cfg.write_text("---\nteam: acme\norg: acme-org\n---\n")

    def shai(self, repo):
        d = self.run_dir / repo
        d.mkdir(parents=True, exist_ok=True)
        r = run(CLI, "--repo", self.repos / repo, "--output", d / "shai-hulud.json")
        (d / "shai-hulud.txt").write_text(r.stdout + r.stderr)

    def generate(self, *extra):
        r = run(GENERATE, "--results-dir", self.run_dir, "--config", self.cfg, "--out-dir", self.run_dir,
                "--repos-root", self.repos, "--home", self.tmp / "home", *extra)
        self.assertIn(r.returncode, (0,), r.stdout + r.stderr)
        doc = json.loads((self.run_dir / "security-report.json").read_text())
        md = (self.run_dir / "security-report.md").read_text()
        page = (self.run_dir / "security-report.html").read_text()
        return doc, md, page

    def section(self, md):
        self.assertIn("## 🪱 Shai-Hulud check", md)
        return md.split("## 🪱 Shai-Hulud check")[1].split("\n## ")[0]

    def test_every_target_gets_a_row_with_its_verdict(self):
        for repo in ("infected", "hooky", "clean"):
            self.shai(repo)
        (self.run_dir / "broken").mkdir()
        (self.run_dir / "broken" / "shai-hulud.txt").write_text("shai-hulud-scan: not a directory: /x\n")
        (self.run_dir / "nocheck").mkdir()
        (self.run_dir / "nocheck" / "semgrep.json").write_text('{"results": []}')
        doc, md, page = self.generate()
        by = dict((t["repo"], t) for t in doc["shai_hulud"]["targets"])
        self.assertEqual(dict((k, v["verdict"]) for k, v in by.items()),
                         {"infected": "affected", "hooky": "suspicious", "clean": "clean", "broken": "error",
                          "nocheck": "not-run"})
        self.assertIn("not a directory", by["broken"]["error"])
        self.assertEqual(by["clean"]["raw"], "clean/shai-hulud.txt")
        self.assertTrue(by["clean"]["checked"]["dependency_files"])
        self.assertEqual(doc["shai_hulud"]["ioc_version"], by["clean"]["checked"]["ioc_version"])
        sec = self.section(md)
        for word in ("🔴 AFFECTED", "🟡 SUSPICIOUS", "🟢 CLEAN", "⚠️ ERROR", "⏭️ not run", "infected", "hooky",
                     "clean", "broken", "nocheck", "references/remediation.md"):
            self.assertIn(word, sec, word)
        self.assertIn("package-lock.json", sec)
        self.assertIn('id="shai-hulud"', page)
        self.assertIn('href="clean/shai-hulud.txt"', page)
        self.assertIn("Shai-Hulud", page.split('class="footer"')[1])
        self.assertEqual(run(VALIDATE, self.run_dir / "security-report.json").returncode, 0)

    def test_clean_repo_with_nothing_to_check_says_so(self):
        (self.repos / "docs-only").mkdir()
        (self.repos / "docs-only" / "README.md").write_text("hi\n")
        self.shai("docs-only")
        doc, md, page = self.generate()
        self.assertIn("nothing to check", self.section(md))

    def test_host_row(self):
        home = self.tmp / "home"
        (home / "code" / "app").mkdir(parents=True)
        shutil.copy(str(FIX / "clean" / "package.json"), str(home / "code" / "app" / "package.json"))
        (home / ".npmrc").write_text("//registry.npmjs.org/:_authToken=%s\n" % NPM_TOKEN)
        d = self.run_dir / "_host"
        d.mkdir(parents=True)
        env = dict(os.environ, HOME=str(home), npm_config_cache=str(home / ".npm"))
        r = run(CLI, "--host", "--root", home, "--output", d / "shai-hulud.json", env=env)
        (d / "shai-hulud.txt").write_text(r.stdout)
        doc, md, page = self.generate()
        host = [t for t in doc["shai_hulud"]["targets"] if t["mode"] == "host"][0]
        self.assertEqual((host["repo"], host["verdict"]), ("this machine", "clean"))
        self.assertEqual(host["credential_stores"], ["~/.npmrc"])
        sec = self.section(md)
        self.assertIn("this machine", sec)
        self.assertIn("~/.npmrc", sec)
        for text in (md, page, json.dumps(doc)):
            self.assertNotIn(NPM_TOKEN, text)

    def test_section_when_the_check_did_not_run(self):
        (self.run_dir / "api").mkdir(parents=True)
        (self.run_dir / "api" / "semgrep.json").write_text('{"results": []}')
        doc, md, page = self.generate()
        self.assertFalse(doc["shai_hulud"]["ran"])
        self.assertIn("did not run in this scan", self.section(md))

    def test_validator_catches_a_verdict_that_contradicts_the_findings(self):
        import report_schema
        self.shai("infected")
        self.shai("clean")
        doc, md, page = self.generate()
        self.assertEqual(report_schema.validate(doc), [])
        bad = json.loads(json.dumps(doc))
        for t in bad["shai_hulud"]["targets"]:
            if t["repo"] == "infected":
                t["verdict"] = "clean"
        self.assertTrue(any("shai_hulud" in e for e in report_schema.validate(bad)))
        bad = json.loads(json.dumps(doc))
        bad["shai_hulud"]["targets"][0]["verdict"] = "maybe"
        self.assertTrue(report_schema.validate(bad))
        bad = json.loads(json.dumps(doc))
        del bad["shai_hulud"]
        self.assertTrue(any("shai_hulud" in e for e in report_schema.validate(bad)))

    def test_failed_check_never_marks_the_previous_finding_fixed(self):
        self.shai("infected")
        first, _, _ = self.generate()
        self.assertEqual([t["verdict"] for t in first["shai_hulud"]["targets"]], ["affected"])
        later = self.tmp / "ws" / "security-run-20261103-100000"
        (later / "infected").mkdir(parents=True)
        (later / "infected" / "shai-hulud.txt").write_text("shai-hulud-scan: indicator file missing\n")
        r = run(GENERATE, "--results-dir", later, "--config", self.cfg, "--out-dir", later,
                "--repos-root", self.repos, "--home", self.tmp / "home")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        doc = json.loads((later / "security-report.json").read_text())
        self.assertEqual(doc["run"]["previous_run"], str(self.run_dir.resolve()))
        self.assertEqual(doc["fixed"], [])
        self.assertEqual(doc["shai_hulud"]["targets"][0]["verdict"], "error")


if __name__ == "__main__":
    unittest.main()
