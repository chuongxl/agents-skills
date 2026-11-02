#!/usr/bin/env python3
"""Offline self-tests for the Shai-Hulud supply-chain detector.

Run: python3 -I scripts/test-shai-hulud.py [TestClass ...] [-v]

No network, no scanner binaries. Fixtures under tests/fixtures/shai-hulud/ are inert:
they contain matching names and strings, never a working payload.
Stdlib only; Python 3.8+.
"""

import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SKILL_DIR / "scripts" / "lib"))

from shaihulud import iocs  # noqa: E402

FIX = SKILL_DIR / "tests" / "fixtures" / "shai-hulud"
IOC_FILE = SKILL_DIR / "assets" / "ioc" / "shai-hulud.json"
CLI = SKILL_DIR / "scripts" / "shai-hulud-scan.py"


def write_iocs(tmp, extra_packages=()):
    """Copy the committed indicator file to tmp, optionally adding packages; return its path."""
    data = json.loads(IOC_FILE.read_text())
    for p in extra_packages:
        data["packages"].append(p)
    path = Path(tmp) / "iocs.json"
    path.write_text(json.dumps(data))
    return path


class IocTests(unittest.TestCase):
    def test_committed_file_is_valid(self):
        self.assertEqual(iocs.validate(json.loads(IOC_FILE.read_text())), [])

    def test_package_index_lowercases_and_keeps_scope(self):
        ioc = iocs.load(str(IOC_FILE))
        self.assertIn(("npm", "@accordproject/concerto-linter"), ioc.packages)
        self.assertEqual(ioc.packages[("npm", "@accordproject/concerto-linter")]["3.24.1"], "sh-2.0")

    def test_validate_rejects_unknown_wave(self):
        data = json.loads(IOC_FILE.read_text())
        data["packages"].append({"ecosystem": "npm", "name": "x", "versions": ["1.0.0"], "wave": "nope"})
        errors = iocs.validate(data)
        self.assertEqual(len(errors), 1)
        self.assertIn("unknown wave", errors[0])

    def test_validate_rejects_bad_ecosystem_and_empty_versions(self):
        data = json.loads(IOC_FILE.read_text())
        data["packages"].append({"ecosystem": "maven", "name": "x", "versions": [], "wave": "sh-2.0"})
        self.assertEqual(len(iocs.validate(data)), 2)

    def test_env_override_wins(self):
        tmp = tempfile.mkdtemp()
        try:
            path = write_iocs(tmp, [{"ecosystem": "pypi", "name": "Evil_Pkg", "versions": ["9.9.9"], "wave": "mini-2026"}])
            old = os.environ.get("SHAI_HULUD_IOCS")
            os.environ["SHAI_HULUD_IOCS"] = str(path)
            try:
                ioc = iocs.load()
            finally:
                if old is None:
                    del os.environ["SHAI_HULUD_IOCS"]
                else:
                    os.environ["SHAI_HULUD_IOCS"] = old
            self.assertIn(("pypi", "evil-pkg"), ioc.packages)  # PEP 503 normalised
        finally:
            shutil.rmtree(tmp)

    def test_generic_payload_requires_hash(self):
        ioc = iocs.load(str(IOC_FILE))
        self.assertTrue(ioc.files["bundle.js"]["sha256"])
        self.assertEqual(ioc.files["bun_environment.js"]["sha256"], [])

    def test_allowlist_loads(self):
        rules = iocs.load_allowlist()
        self.assertTrue(any(r.matches("node-gyp rebuild", "anything") for r in rules))
        self.assertTrue(any(r.matches("node install.js", "esbuild") for r in rules))
        self.assertFalse(any(r.matches("node install.js", "evil-helper") for r in rules))

    def test_every_wave_has_reference(self):
        ioc = iocs.load(str(IOC_FILE))
        for wid, wave in ioc.waves.items():
            self.assertTrue(wave.get("references"), wid)


if __name__ == "__main__":
    unittest.main()
