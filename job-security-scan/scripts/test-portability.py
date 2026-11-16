#!/usr/bin/env python3
"""test-portability.py - keep the skill's Python runnable on macOS, Linux and Windows.

Static checks over scripts/**/*.py (stdlib only):
  * text-mode open()/read_text()/write_text() must name an encoding (Windows defaults to a legacy code page and
    crashes or corrupts UTF-8 files: names, comments and rule text are UTF-8);
  * subprocess text=True / universal_newlines=True must name an encoding for the same reason;
  * POSIX-only os/signal names must not be touched at import time (only inside a platform-gated function).
"""
import ast
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
POSIX_ONLY = {"O_NOFOLLOW", "O_NONBLOCK", "O_DIRECTORY", "getuid", "geteuid", "fork", "setsid", "chown", "killpg"}


def py_files():
    return sorted(p for p in (SKILL_DIR / "scripts").rglob("*.py") if not p.name.startswith("test-")
                  and "__pycache__" not in p.parts)


def kw(call, name):
    return next((k for k in call.keywords if k.arg == name), None)


def is_binary_open(call):
    mode = call.args[1] if len(call.args) > 1 else getattr(kw(call, "mode"), "value", None)
    return isinstance(mode, ast.Constant) and isinstance(mode.value, str) and "b" in mode.value


def problems(path):
    tree = ast.parse(path.read_text(encoding="utf-8"), str(path))
    out = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        f = node.func
        name = f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else ""
        has_enc = kw(node, "encoding") is not None
        if name == "open" and isinstance(f, ast.Name) and not has_enc and not is_binary_open(node):
            out.append((node.lineno, "open() without encoding"))
        elif name in ("read_text", "write_text") and isinstance(f, ast.Attribute) and not has_enc:
            out.append((node.lineno, "%s() without encoding" % name))
        elif name in ("run", "check_output", "Popen") and not has_enc:
            for flag in ("text", "universal_newlines"):
                k = kw(node, flag)
                if k is not None and isinstance(k.value, ast.Constant) and k.value.value is True:
                    out.append((node.lineno, "subprocess %s=True without encoding" % flag))
    for node in tree.body:   # module level only: anything inside a function is gated by its caller
        for sub in ast.walk(node):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                break
            if isinstance(sub, ast.Attribute) and sub.attr in POSIX_ONLY and isinstance(sub.value, ast.Name) \
                    and sub.value.id in ("os", "signal"):
                out.append((sub.lineno, "POSIX-only %s.%s at import time" % (sub.value.id, sub.attr)))
    return out


class PortabilityTests(unittest.TestCase):
    def test_no_platform_specific_python(self):
        bad = ["%s:%d: %s" % (p.relative_to(SKILL_DIR), n, why) for p in py_files() for n, why in problems(p)]
        self.assertEqual(bad, [], "\n" + "\n".join(bad))


@unittest.skipUnless(shutil.which("bash"), "bash required")
class FindPythonTests(unittest.TestCase):
    """scripts/lib/find-python.sh: skips a python3 that does not run (Windows Store stub), finds `python`,
    and strips Windows line endings from py() output while keeping Python's exit status."""

    def sh(self, script, path_dirs, env_extra=None):
        env = dict(os.environ, PATH=os.pathsep.join(path_dirs) + os.pathsep + os.path.dirname(shutil.which("bash")) + os.pathsep + "/usr/bin" + os.pathsep + "/bin")
        env.pop("PY", None)
        env.update(env_extra or {})
        return subprocess.run(["bash", "-c", '. "%s"; %s' % (SKILL_DIR / "scripts" / "lib" / "find-python.sh", script)],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, env=env)

    def stub(self, d, name, body):
        p = Path(d) / name
        p.write_text("#!/bin/sh\n" + body)
        p.chmod(0o755)

    def test_broken_python3_is_skipped_and_crlf_is_stripped(self):
        with tempfile.TemporaryDirectory() as d:
            self.stub(d, "python3", "echo 'Python was not found' >&2; exit 49")          # Microsoft Store stub
            self.stub(d, "python", 'case "$1" in -c) exit 0;; esac; printf "ok\\r\\n"; exit 3')   # CRLF + status 3
            r = self.sh('echo "PY=$PY"; v=$(py x); echo "[$v]"; py x >/dev/null; echo "rc=$?"', [d])
        self.assertIn("PY=python\n", r.stdout)
        self.assertIn("[ok]", r.stdout)
        self.assertIn("rc=3", r.stdout)

    def test_no_python_gives_a_clear_error(self):
        with tempfile.TemporaryDirectory() as d:
            self.stub(d, "python3", "exit 1")
            r = self.sh("true", [d])
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("Python 3.8+ not found", r.stderr)


if __name__ == "__main__":
    unittest.main()
