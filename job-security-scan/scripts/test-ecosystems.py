#!/usr/bin/env python3
"""Offline self-tests for ecosystem detection and scanner wiring.

Run: python3 -I scripts/test-ecosystems.py

These tests need no network and no scanner binaries (scanners are stubbed on PATH).
The real-tool end-to-end test is tests/e2e/run-e2e.sh.
Stdlib only; Python 3.8+.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(SKILL_DIR, "scripts", "lib"))

import ecosystems  # noqa: E402

FIX = os.path.join(SKILL_DIR, "tests", "fixtures")
DETECT = os.path.join(SKILL_DIR, "scripts", "detect-ecosystems.py")
RUN_SCAN = os.path.join(SKILL_DIR, "scripts", "run-scan.sh")
DESCRIPTORS = ecosystems.load_descriptors()


def ids(result):
    return [e["id"] for e in result["ecosystems"]]


class DescriptorTests(unittest.TestCase):
    def test_all_shipped_descriptors_load(self):
        self.assertEqual(
            sorted(d["id"] for d in DESCRIPTORS),
            ["dotnet", "go", "java-gradle", "java-maven", "node", "php", "python", "ruby", "rust"])

    def test_every_descriptor_has_osv_ecosystem_and_semgrep(self):
        for d in DESCRIPTORS:
            self.assertTrue(d["osv_ecosystem"], d["id"])
            self.assertTrue(d["semgrep"], d["id"])

    def test_invalid_descriptors_rejected(self):
        good = dict(DESCRIPTORS[0])
        cases = {
            "unknown field": dict(good, bogus=1),
            "bad id": dict(good, id="Bad_ID"),
            "no detect": dict(good, detect=[]),
            "path in detect": dict(good, detect=["src/pom.xml"]),
            "no osv": {k: v for k, v in good.items() if k != "osv_ecosystem"},
            "bad schema_version": dict(good, schema_version=True),
            "bad semgrep": dict(good, semgrep=["python"]),
            "bad extractor": dict(good, runtime={"name": "x", "extractors": [{"file": "f"}]}),
            "regex without group": dict(good, runtime={"name": "x", "extractors": [{"file": "f", "regex": "abc"}]}),
        }
        for label, d in cases.items():
            self.assertTrue(ecosystems.validate_descriptor(d), label)

    def test_loader_reports_file_name_mismatch_and_duplicates(self):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d)
        src = dict(DESCRIPTORS[0])
        json.dump(dict(src, id="other"), open(os.path.join(d, "node.json"), "w"))
        with self.assertRaises(ecosystems.EcosystemError) as cm:
            ecosystems.load_descriptors(d)
        self.assertIn("must match the file name", str(cm.exception))

    def test_new_ecosystem_needs_only_one_file(self):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d)
        for f in os.listdir(ecosystems.default_dir()):
            shutil.copy(os.path.join(ecosystems.default_dir(), f), d)
        json.dump({"schema_version": 1, "id": "elixir", "name": "Elixir", "detect": ["mix.exs"],
                   "lockfiles": ["mix.lock"], "osv_ecosystem": "Hex", "semgrep": ["p/elixir"]},
                  open(os.path.join(d, "elixir.json"), "w"))
        repo = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, repo)
        open(os.path.join(repo, "mix.exs"), "w").write("")
        open(os.path.join(repo, "mix.lock"), "w").write("")
        r = ecosystems.detect(repo, ecosystems.load_descriptors(d))
        self.assertEqual(ids(r), ["elixir"])
        self.assertEqual(r["lockfiles"], ["mix.lock"])
        self.assertFalse(r["needs_sbom"])


class DetectTests(unittest.TestCase):
    def detect(self, name):
        return ecosystems.detect(os.path.join(FIX, name), DESCRIPTORS)

    def test_maven(self):
        r = self.detect("maven-log4j")
        self.assertEqual(ids(r), ["java-maven"])
        self.assertEqual(r["lockfiles"], ["pom.xml"])
        self.assertIn("p/java", r["semgrep"])

    def test_python(self):
        r = self.detect("python-django")
        self.assertEqual((ids(r), r["lockfiles"]), (["python"], ["requirements.txt"]))

    def test_go(self):
        r = self.detect("go-text")
        self.assertEqual((ids(r), r["lockfiles"]), (["go"], ["go.mod"]))

    def test_node_yarn(self):
        r = self.detect("node-lodash")
        self.assertEqual((ids(r), r["lockfiles"]), (["node"], ["yarn.lock"]))
        self.assertFalse(r["needs_sbom"])

    def test_monorepo_finds_nested_ecosystems(self):
        r = self.detect("monorepo")
        self.assertEqual(sorted(ids(r)), ["java-maven", "node"])
        self.assertEqual(r["lockfiles"], ["services/api/pom.xml", "web/yarn.lock"])

    def test_unmapped_stack_needs_sbom(self):
        r = self.detect("unmapped-swift")
        self.assertEqual(ids(r), [])
        self.assertTrue(r["needs_sbom"])

    def test_manifest_without_lockfile_needs_sbom(self):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d)
        open(os.path.join(d, "build.gradle"), "w").write("")
        r = ecosystems.detect(d, DESCRIPTORS)
        self.assertEqual(ids(r), ["java-gradle"])
        self.assertTrue(r["needs_sbom"])

    def test_dependency_directories_are_skipped(self):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d)
        for sub in ("node_modules/x", "vendor/y", "target/z", ".venv/w"):
            os.makedirs(os.path.join(d, sub))
            for f in ("package.json", "composer.json", "pom.xml", "requirements.txt"):
                open(os.path.join(d, sub, f), "w").write("")
        self.assertEqual(ids(ecosystems.detect(d, DESCRIPTORS)), [])

    def test_depth_limit(self):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d)
        deep = os.path.join(d, "a", "b", "c", "d", "e")
        os.makedirs(deep)
        open(os.path.join(deep, "go.mod"), "w").write("")
        self.assertEqual(ids(ecosystems.detect(d, DESCRIPTORS, max_depth=4)), [])
        self.assertEqual(ids(ecosystems.detect(d, DESCRIPTORS, max_depth=6)), ["go"])

    def test_glob_detection_dotnet(self):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d)
        open(os.path.join(d, "App.csproj"), "w").write("")
        self.assertEqual(ids(ecosystems.detect(d, DESCRIPTORS)), ["dotnet"])

    def test_not_a_directory(self):
        with self.assertRaises(ecosystems.EcosystemError):
            ecosystems.detect("/nonexistent-dir", DESCRIPTORS)


class CliTests(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, "-I", DETECT] + list(args), capture_output=True, text=True)

    def test_formats(self):
        p = os.path.join(FIX, "monorepo")
        self.assertEqual(self.run_cli(p, "--format", "lockfiles").stdout.split(), ["services/api/pom.xml", "web/yarn.lock"])
        self.assertEqual(self.run_cli(p, "--format", "ids").stdout.split(), ["java-maven", "node"])
        self.assertEqual(self.run_cli(p, "--format", "needs-sbom").stdout.strip(), "false")
        self.assertEqual(self.run_cli(os.path.join(FIX, "unmapped-swift"), "--format", "needs-sbom").stdout.strip(), "true")
        self.assertIn("p/java", self.run_cli(p, "--format", "semgrep").stdout.split())
        self.assertEqual(json.loads(self.run_cli(p, "--format", "json").stdout)["lockfiles"][0], "services/api/pom.xml")

    def test_validate_and_errors(self):
        self.assertEqual(self.run_cli("--validate").returncode, 0)
        self.assertEqual(self.run_cli("/nonexistent-dir").returncode, 2)
        self.assertEqual(self.run_cli("--ecosystems", "/nonexistent-dir", "--validate").returncode, 2)


@unittest.skipUnless(shutil.which("bash"), "bash required")
class ScannerWiringTests(unittest.TestCase):
    """run-scan.sh with stub osv-scanner/trivy on PATH: checks arguments, not vulnerabilities."""

    def setUp(self):
        self.work = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.work)
        self.bin = os.path.join(self.work, "bin")
        os.makedirs(self.bin)
        self.calls = os.path.join(self.work, "calls.log")
        stub = '#!/usr/bin/env bash\necho "$(basename "$0") $*" >> "%s"\n' % self.calls
        # osv-scanner stub writes a report to the --output path
        osv = stub + ('out=""; prev=""; for a in "$@"; do [ "$prev" = "--output" ] && out="$a"; prev="$a"; done\n'
                      '[ -n "$out" ] && echo \'{"results":[]}\' > "$out"\nexit 0\n')
        trivy = stub + ('out=""; prev=""; for a in "$@"; do [ "$prev" = "--output" ] && out="$a"; prev="$a"; done\n'
                        '[ -n "$out" ] && echo \'{"components":[{"name":"x"}]}\' > "$out"\nexit 0\n')
        for name, body in (("osv-scanner", osv), ("trivy", trivy)):
            path = os.path.join(self.bin, name)
            open(path, "w").write(body)
            os.chmod(path, 0o755)
        self.config = os.path.join(self.work, "repository.md")
        repos = "".join("  - name: %s\n    active: true\n    has-dockerfile: false\n" % n
                        for n in ("monorepo", "unmapped-swift", "go-text"))
        open(self.config, "w").write(
            '---\nteam: t\norg: o\nmonorepo-root: "%s"\nci-runner: x\nfail-on-severity: HIGH\n'
            'output-dir: "%s"\nrepos:\n%s---\n' % (FIX, os.path.join(self.work, "out"), repos))

    def scan(self, scanner):
        env = dict(os.environ, PATH=self.bin + os.pathsep + os.environ["PATH"])
        r = subprocess.run(["bash", RUN_SCAN, "--config", self.config, "--scanner", scanner],
                           capture_output=True, text=True, env=env, cwd=self.work)
        calls = open(self.calls).read() if os.path.exists(self.calls) else ""
        return r, calls

    def test_osv_scans_every_detected_lockfile_without_hardcoding_yarn(self):
        r, calls = self.scan("osv")
        self.assertIn("-L %s/monorepo/services/api/pom.xml" % FIX, calls)
        self.assertIn("-L %s/monorepo/web/yarn.lock" % FIX, calls)
        self.assertIn("-L %s/go-text/go.mod" % FIX, calls)
        self.assertNotIn("--lockfile", calls)
        self.assertIn("no supported lockfile found", r.stdout)  # unmapped-swift

    def test_sbom_fallback_only_for_unmapped_repo(self):
        r, calls = self.scan("sbom")
        sbom_calls = [c for c in calls.splitlines() if c.startswith("trivy")]
        self.assertEqual(len(sbom_calls), 1, calls)
        self.assertIn("unmapped-swift", sbom_calls[0])
        self.assertIn("--format cyclonedx", sbom_calls[0])
        self.assertIn("--sbom", calls)
        self.assertIn("every detected ecosystem has a lockfile", r.stdout)

    def test_semgrep_gets_detected_rulesets_without_stack(self):
        semgrep = os.path.join(self.bin, "semgrep")
        with open(semgrep, "w") as fh:
            fh.write('#!/usr/bin/env bash\necho "semgrep $*" >> "%s"\n'
                     'out=""; prev=""; for a in "$@"; do [ "$prev" = "--output" ] && out="$a"; prev="$a"; done\n'
                     '[ -n "$out" ] && echo \'{"results":[]}\' > "$out"\nexit 0\n' % self.calls)
        os.chmod(semgrep, 0o755)
        _r, calls = self.scan("semgrep")
        mono = [c for c in calls.splitlines() if c.endswith("/monorepo")][0]
        for rs in ("p/java", "p/javascript", "p/typescript", "p/owasp-top-ten", "p/secrets"):
            self.assertIn("--config %s" % rs, mono)
        self.assertNotIn("p/golang", mono)
        go = [c for c in calls.splitlines() if c.endswith("/go-text")][0]
        self.assertIn("--config p/golang", go)


class ConfigDeprecationTests(unittest.TestCase):
    def parse(self, frontmatter):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d)
        path = os.path.join(d, "repository.md")
        with open(path, "w") as fh:
            fh.write("---\n%s\n---\n" % frontmatter)
        return subprocess.run([sys.executable, "-I", os.path.join(SKILL_DIR, "scripts", "parse-config.py"), path],
                              capture_output=True, text=True)

    def test_legacy_fields_warn_but_still_work(self):
        r = self.parse("team: t\npackage-manager: yarn\nstack:\n  - typescript\nrepos:\n  - name: a\n    active: true")
        self.assertEqual(r.returncode, 0)
        self.assertIn("'package-manager'", r.stderr)
        self.assertIn("'stack'", r.stderr)
        self.assertIn("p/typescript", r.stdout)

    def test_no_warning_without_legacy_fields(self):
        r = self.parse("team: t\nrepos:\n  - name: a\n    active: true")
        self.assertEqual(r.returncode, 0)
        self.assertEqual(r.stderr, "")
        self.assertIn("p/owasp-top-ten", r.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=1)
