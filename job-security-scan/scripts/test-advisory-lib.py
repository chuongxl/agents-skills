#!/usr/bin/env python3
"""Self-tests for the advisory libraries. Run: python3 -I scripts/test-advisory-lib.py

Stdlib only (unittest); Python 3.8+.
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(SKILL_DIR, "scripts", "lib"))

import advisory  # noqa: E402
import component as comp  # noqa: E402
import sources  # noqa: E402

SCHEMA = advisory.load_json(os.path.join(SKILL_DIR, "assets", "advisory.schema.json"))
CLI = os.path.join(SKILL_DIR, "scripts", "validate-advisories.py")


class PurlTests(unittest.TestCase):
    def test_versionless_scoped_purl(self):
        p = comp.parse_purl("pkg:npm/@nestjs/core")
        self.assertEqual((p["namespace"], p["name"], p["version"]), ("@nestjs", "core", None))

    def test_scoped_purl_spellings_agree(self):
        a = comp.canonical_purl("pkg:npm/@nestjs/core@10.0.0")
        b = comp.canonical_purl("pkg:npm/%40nestjs/core@10.0.0")
        self.assertEqual(a, b)
        self.assertEqual(comp.parse_purl(a)["version"], "10.0.0")

    def test_version_at_sign_only_after_last_slash(self):
        self.assertEqual(comp.parse_purl("pkg:npm/foo@1.2.3")["version"], "1.2.3")
        with self.assertRaises(comp.PurlError):
            comp.parse_purl("pkg:npm/foo@")

    def test_pattern_with_scope_matches(self):
        c = comp.Component("package", "npm", "core", "1", "pkg:npm/@nestjs/core@1")
        self.assertTrue(comp.matches_pattern(c, "pkg:npm/@nestjs/*"))
        self.assertTrue(comp.matches_pattern(c, "pkg:npm/%40nestjs/*"))
        self.assertFalse(comp.matches_pattern(c, "pkg:npm/@other/*"))


class SchemaTests(unittest.TestCase):
    def test_const_is_type_strict(self):
        s = {"const": 1}
        self.assertEqual(advisory.validate_schema(1, s), [])
        self.assertTrue(advisory.validate_schema(True, s))
        self.assertTrue(advisory.validate_schema(1.0, s))

    def test_pattern_rejects_trailing_newline(self):
        s = {"type": "string", "pattern": "^abc$"}
        self.assertEqual(advisory.validate_schema("abc", s), [])
        self.assertTrue(advisory.validate_schema("abc\n", s))

    def test_sources_schema_version_not_bool(self):
        self.assertTrue(any("schema_version" in e for e in sources.validate_sources({"schema_version": True})))


class SourceCheckTests(unittest.TestCase):
    def test_first_request_is_allowlist_checked(self):
        r = sources.check_url("https://evil.example.com/x", {"nodejs.org"})
        self.assertFalse(r["ok"])
        self.assertIn("not allowlisted", r["note"])
        r = sources.check_url("http://nodejs.org/x", {"nodejs.org"})
        self.assertIn("not https", r["note"])


class CliTests(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, "-I", CLI] + list(args), capture_output=True, text=True)

    def test_default_scan_passes_and_prints_relative_paths(self):
        r = self.run_cli()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotIn(SKILL_DIR + os.sep, r.stdout.replace(os.getcwd() + os.sep, ""))

    def test_examples_are_outside_the_scan_tree(self):
        for dirpath, _d, files in os.walk(os.path.join(SKILL_DIR, "assets", "advisories")):
            for f in files:
                data = advisory.load_json(os.path.join(dirpath, f))
                for a in data["advisories"]:
                    self.assertFalse(a["id"].startswith("PENDING-"), "example leaked into scan tree")
                    self.assertNotEqual(a["source"].get("approved_by"), "example-only")

    def test_check_sources_skipped_when_registry_invalid(self):
        d = tempfile.mkdtemp()
        bad = os.path.join(d, "sources.json")
        json.dump({"schema_version": 1, "allowed_hosts": ["nodejs.org"], "vendors": [], "aggregators": []}, open(bad, "w"))
        r = self.run_cli("--sources", bad, "--check-sources")
        self.assertEqual(r.returncode, 1)
        self.assertIn("skipping --check-sources", r.stderr)
        self.assertNotIn("FAIL ", r.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=1)
