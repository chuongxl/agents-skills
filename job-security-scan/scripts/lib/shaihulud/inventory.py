"""Packages present in a directory tree: lockfile entries, installed node_modules, PyPI pins.

Parsers are line-based and forgiving: a malformed or binary file yields nothing, never raises.
"""

import json
import os
import re
from collections import namedtuple
from pathlib import Path

from .iocs import normalize_name

Pkg = namedtuple("Pkg", "ecosystem name version location")

SKIP_DIRS = {".git", ".hg", ".svn"}
NPM_LOCKS = ("package-lock.json", "npm-shrinkwrap.json")
MAX_LOCK_BYTES = 50 * 1024 * 1024
_VERSION = re.compile(r"^\d+\.\d+")


def _read_text(path):
    try:
        if os.path.getsize(path) > MAX_LOCK_BYTES:
            return None
        with open(path, "r", encoding="utf-8", errors="strict") as fh:
            text = fh.read()
    except (OSError, UnicodeDecodeError):
        return None
    if "\x00" in text:
        return None
    return text


def _read_json(path):
    text = _read_text(path)
    if text is None:
        return None
    try:
        data = json.loads(text)
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


FIXTURE_MARKER = ".shai-hulud-test-fixtures"


def is_skill_fixture_dir(path):
    """True for this skill's own inert test fixtures (wherever the skill is installed): the directory
    holds FIXTURE_MARKER *and* sits under a tests/fixtures path. Both are required, so a marker file
    planted in an arbitrary package directory does not hide it."""
    parts = Path(path).parts
    under_fixtures = any(a == "tests" and b == "fixtures" for a, b in zip(parts, parts[1:]))
    return under_fixtures and os.path.isfile(os.path.join(str(path), FIXTURE_MARKER))


def prune(dirpath, dirnames, skip=SKIP_DIRS):
    """Filter os.walk dirnames in place: VCS/skip dirs and the skill's own test fixtures."""
    dirnames[:] = [d for d in dirnames if d not in skip and not is_skill_fixture_dir(os.path.join(dirpath, d))]


def _walk(root):
    """os.walk without following symlinks, entering VCS dirs, or entering this skill's test fixtures."""
    for dirpath, dirnames, filenames in os.walk(str(root), followlinks=False):
        prune(dirpath, dirnames)
        yield Path(dirpath), filenames


def _rel(root, path):
    rel = os.path.relpath(str(path), str(root))
    return "." if rel == "." else rel.replace(os.sep, "/")


def _in_node_modules(rel_dir):
    return "node_modules" in rel_dir.split("/")


def _is_package_dir(rel_dir):
    """True for node_modules/<name> and node_modules/@scope/<name>."""
    parts = rel_dir.split("/")
    if len(parts) >= 2 and parts[-2] == "node_modules" and not parts[-1].startswith((".", "@")):
        return True
    return len(parts) >= 3 and parts[-3] == "node_modules" and parts[-2].startswith("@")


# ── npm lockfiles ────────────────────────────────────────────────────────────

def _parse_package_lock(data):
    packages = data.get("packages")
    if isinstance(packages, dict):
        for key, meta in packages.items():
            if not key or not isinstance(meta, dict) or "node_modules/" not in key:
                continue
            if meta.get("link"):
                continue
            name = meta.get("name") or key.rsplit("node_modules/", 1)[1]
            version = meta.get("version")
            if isinstance(version, str) and _VERSION.match(version):
                yield name, version
        return

    def walk(deps):
        for name, meta in (deps or {}).items():
            if not isinstance(meta, dict):
                continue
            version = meta.get("version", "")
            if version.startswith("npm:"):              # v1 alias: "npm:real@1.2.3"
                real, _, version = version[4:].rpartition("@")
                name = real or name
            if _VERSION.match(version):
                yield name, version
            for item in walk(meta.get("dependencies")):
                yield item
    for item in walk(data.get("dependencies")):
        yield item


def _yarn_spec_name(spec):
    """'name@range', '@s/name@range', 'alias@npm:real@range' or 'name@npm:range' -> package name."""
    spec = spec.strip().strip('"')
    if "@npm:" in spec:
        alias, right = spec.split("@npm:", 1)
        return right.rpartition("@")[0] if right.rfind("@") > 0 else alias
    return spec.rpartition("@")[0] if spec.rfind("@") > 0 else spec


def _parse_yarn_lock(text):
    name = version = resolution = None

    def flush():
        if resolution:                       # yarn berry: trust the resolved locator
            if "@npm:" not in resolution:    # workspace:, patch:, git, file: - not a registry release
                return None
            real, _, ver = resolution.rpartition("@npm:")
            return (real, ver) if real and _VERSION.match(ver) else None
        if name and version and _VERSION.match(version):
            return name, version
        return None

    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if not line.startswith(" "):
            item = flush()
            if item:
                yield item
            header = line.rstrip(":").strip()
            name = None if header == "__metadata" else _yarn_spec_name(header.split(",")[0])
            version = resolution = None
            continue
        stripped = line.strip()
        if stripped.startswith("version"):
            version = stripped[len("version"):].lstrip(": ").strip().strip('"')
        elif stripped.startswith("resolution:"):
            resolution = stripped[len("resolution:"):].strip().strip('"')
    item = flush()
    if item:
        yield item


def _parse_pnpm_lock(text):
    section = None
    for line in text.splitlines():
        if line and not line.startswith(" "):
            section = line.rstrip(":").strip()
            continue
        if section not in ("packages", "snapshots"):
            continue
        if not line.startswith("  ") or line.startswith("   ") or not line.rstrip().endswith(":"):
            continue
        key = line.strip().rstrip(":").strip("'\"").lstrip("/")
        key = key.split("(", 1)[0]
        if key.rfind("@") > 0:
            name, _, version = key.rpartition("@")
        else:
            name, _, version = key.rpartition("/")
        if name and _VERSION.match(version):
            yield name, version


# ── PyPI ─────────────────────────────────────────────────────────────────────

_REQ = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)\s*(?:\[[^\]]*\])?\s*===?\s*([0-9][^\s;#,]*)")


def _parse_requirements(text):
    for line in text.splitlines():
        m = _REQ.match(line)
        if m:
            yield m.group(1), m.group(2)


def _parse_toml_packages(text):
    name = None
    for line in text.splitlines():
        s = line.strip()
        if s == "[[package]]":
            name = None
        elif s.startswith("name = "):
            name = s[7:].strip().strip('"')
        elif s.startswith("version = ") and name:
            version = s[10:].strip().strip('"')
            if _VERSION.match(version):
                yield name, version
            name = None


# ── public API ───────────────────────────────────────────────────────────────

def iter_manifests(root):
    """Yield (package_dir, manifest) for the root package.json and every installed package."""
    root = Path(root)
    for dirpath, filenames in _walk(root):
        if "package.json" not in filenames:
            continue
        rel = _rel(root, dirpath)
        # root, installed packages, and nested workspace projects outside node_modules
        if _in_node_modules(rel) and not _is_package_dir(rel):
            continue
        data = _read_json(dirpath / "package.json")
        if data is not None:
            yield dirpath, data


def iter_packages(root, installed=True):
    """Yield every Pkg found under root (deduplicated)."""
    root = Path(root)
    seen = set()

    def emit(ecosystem, name, version, location):
        if not name or not version:
            return None
        pkg = Pkg(ecosystem, normalize_name(ecosystem, name) if ecosystem == "pypi" else name.strip(),
                  version.strip(), location)
        if pkg in seen:
            return None
        seen.add(pkg)
        return pkg

    for dirpath, filenames in _walk(root):
        rel_dir = _rel(root, dirpath)
        inside_nm = _in_node_modules(rel_dir)
        for fn in filenames:
            path = dirpath / fn
            loc = _rel(root, path)
            items, eco = (), "npm"
            if inside_nm:
                if installed and fn == "package.json" and _is_package_dir(rel_dir):
                    data = _read_json(path)
                    if data and isinstance(data.get("name"), str) and isinstance(data.get("version"), str):
                        items = [(data["name"], data["version"])]
            elif fn in NPM_LOCKS:
                data = _read_json(path)
                items = list(_parse_package_lock(data)) if data else ()
            elif fn == "yarn.lock":
                text = _read_text(path)
                items = list(_parse_yarn_lock(text)) if text else ()
            elif fn == "pnpm-lock.yaml":
                text = _read_text(path)
                items = list(_parse_pnpm_lock(text)) if text else ()
            elif fn.startswith("requirements") and fn.endswith(".txt"):
                text = _read_text(path)
                items, eco = (list(_parse_requirements(text)) if text else ()), "pypi"
            elif fn in ("poetry.lock", "uv.lock", "pdm.lock"):
                text = _read_text(path)
                items, eco = (list(_parse_toml_packages(text)) if text else ()), "pypi"
            for name, version in items:
                pkg = emit(eco, name, version, loc)
                if pkg:
                    yield pkg
