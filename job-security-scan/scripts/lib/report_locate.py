"""Locate every finding to a file, a line and one line of code, for the reports.

Scanners that report a line keep it (the code excerpt is read from that line). For findings that point at a
lockfile or manifest without a line (Trivy dependency CVEs, OSV, vendor advisories, Shai-Hulud), the line is
the package's own entry. Other file findings use their evidence text, else line 1.

Secrets never get an excerpt, and credential files are never opened. Every excerpt passes through the
Shai-Hulud redact() as a second guard. Stdlib only; Python 3.8+.
"""

import os
import re
from pathlib import Path

from shaihulud.findings import redact

MAX_BYTES = 25 * 1024 * 1024
WINDOW = 6                                       # lines after a key in which its version must appear
NO_EXCERPT_TYPES = {"secret"}
NO_EXCERPT_RULES = {"credential-store", "credential-permissions"}
HOST_REPO_LABELS = {"this machine", "_host"}


DEPENDENCY_FILES = {
    "package-lock.json", "npm-shrinkwrap.json", "yarn.lock", "pnpm-lock.yaml", "package.json", "bun.lock",
    "poetry.lock", "uv.lock", "pdm.lock", "pipfile.lock", "pyproject.toml", "setup.py", "setup.cfg",
    "go.mod", "go.sum", "cargo.lock", "cargo.toml", "gemfile.lock", "gemfile", "composer.lock", "composer.json",
    "pom.xml", "build.gradle", "build.gradle.kts", "gradle.lockfile", "packages.lock.json", "dockerfile",
}


def is_dependency_file(name):
    low = name.lower()
    return (low in DEPENDENCY_FILES or (low.startswith("requirements") and low.endswith(".txt"))
            or low.endswith((".csproj", ".cdx.json", ".spdx.json")))


def _norm_py(name):
    return re.sub(r"[-_.]+", "-", name.strip().lower())


def resolve(file_field, repo_root, home):
    if not file_field:
        return None
    if file_field.startswith("~/") or file_field == "~":
        return Path(home) / file_field[2:]
    p = Path(file_field)
    if p.is_absolute():
        return p
    return Path(repo_root) / p if repo_root else None


def _read_lines(path):
    try:
        if not path.is_file() or path.is_symlink() or path.stat().st_size > MAX_BYTES:
            return None
        raw = path.read_bytes()
    except OSError:
        return None
    if b"\x00" in raw[:8192]:
        return None
    return raw.decode("utf-8", errors="replace").splitlines()


def _version_near(lines, i, version, window=WINDOW):
    return any(version in l for l in lines[i:i + window + 1])


def _package_line(lines, name, version, filename):
    """1-based line of `name`'s own entry (with `version` where possible), or None."""
    if not name:
        return None
    low = name.lower()
    fn = filename.lower()
    tests = []
    if fn in ("package-lock.json", "npm-shrinkwrap.json"):
        key = '"node_modules/%s"' % name
        tests.append(lambda i, l: l.rstrip().endswith(key + ": {") or (key + ":") in l)
    elif fn == "yarn.lock":
        head = re.compile(r'^"?(?:[^"\s,]+,\s*)*"?%s@' % re.escape(name))
        tests.append(lambda i, l: not l.startswith(" ") and bool(head.match(l)))
    elif fn == "pnpm-lock.yaml":
        tests.append(lambda i, l: ("%s@%s" % (name, version)) in l or ("/%s/%s" % (name, version)) in l)
    elif fn.startswith("requirements") and fn.endswith(".txt"):
        req = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)\s*(?:\[[^\]]*\])?\s*[=~<>!]=")
        tests.append(lambda i, l: bool(req.match(l)) and _norm_py(req.match(l).group(1)) == _norm_py(name))
    elif fn in ("poetry.lock", "uv.lock", "pdm.lock"):
        tests.append(lambda i, l: l.strip().lower().startswith("name = ") and
                     _norm_py(l.split("=", 1)[1].strip().strip('"')) == _norm_py(name))
    for test in tests:
        hits = [i for i, l in enumerate(lines) if test(i, l)]
        for i in hits:
            if not version or _version_near(lines, i, version):
                return i + 1
        if hits:
            return hits[0] + 1
    # generic: a line naming the package and its version, then a line naming the package
    for i, l in enumerate(lines):
        if low in l.lower() and version and version in l:
            return i + 1
    for i, l in enumerate(lines):
        if low in l.lower():
            return i + 1
    return None


def _evidence_line(lines, evidence):
    if not evidence:
        return None
    for piece in [evidence] + [p for p in re.split(r"\s*\.\.\.\s*", evidence) if len(p) >= 6]:
        piece = piece.strip()
        for i, l in enumerate(lines):
            if piece and piece in l:
                return i + 1
    return None


def _excerpt(lines, line):
    if not lines or not line or line < 1 or line > len(lines):
        return ""
    return redact(lines[line - 1].strip())


def locate(finding, repo_root, home):
    """(line, code) for one finding. Never raises; never reads credential files."""
    given = finding.get("line")
    try:
        given = int(given) if given not in (None, "") else None
    except (TypeError, ValueError):
        given = None
    if finding.get("rule_id") in NO_EXCERPT_RULES:
        return None, ""
    if finding.get("type") in NO_EXCERPT_TYPES and given is not None:
        return given, ""  # secret scanners report the line; never reopen a file that holds a secret
    path = resolve(finding.get("file") or "", repo_root, home)
    if path is None:
        return given, ""
    lines = _read_lines(path)
    if lines is None:
        return given, ""
    line = given
    if line is None and finding.get("package"):
        line = _package_line(lines, finding["package"], finding.get("installed_version") or "", path.name)
    if line is None:
        line = _evidence_line(lines, finding.get("evidence") or "")
    if line is None and lines and not (finding.get("package") and is_dependency_file(path.name)):
        line = 1  # a finding about the file itself (payload, planted file): point at its start
    if finding.get("type") in NO_EXCERPT_TYPES:
        return line, ""
    return line, _excerpt(lines, line)


def apply(findings, repos_root, home):
    """Set f['line'] and f['code'] on every finding, in place."""
    for f in findings:
        repo = f.get("repo", "")
        root = None if repo in HOST_REPO_LABELS else Path(repos_root) / repo
        f["line"], f["code"] = locate(f, root, home)
