"""Indicator data for the Shai-Hulud worm family: loading, indexing, validation."""

import json
import os
import re
from pathlib import Path

ASSET_DIR = Path(__file__).resolve().parents[3] / "assets" / "ioc"
DEFAULT_IOCS = ASSET_DIR / "shai-hulud.json"
DEFAULT_ALLOWLIST = ASSET_DIR / "hook-allowlist.json"

ECOSYSTEMS = ("npm", "pypi")
FILE_KINDS = ("payload", "stager")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def normalize_name(ecosystem, name):
    """npm names are case-insensitive in practice; PyPI names follow PEP 503."""
    name = name.strip().lower()
    if ecosystem == "pypi":
        name = re.sub(r"[-_.]+", "-", name)
    return name


class Iocs(object):
    """Indexed indicator set. Build with load()."""

    def __init__(self, data):
        self.version = data.get("version", "")
        self.waves = dict(data.get("waves", {}))
        self.packages = {}
        for p in data.get("packages", []):
            key = (p["ecosystem"], normalize_name(p["ecosystem"], p["name"]))
            versions = self.packages.setdefault(key, {})
            for v in p["versions"]:
                versions.setdefault(v.strip(), p["wave"])
        self.files = {}
        for f in data.get("files", []):
            self.files[f["name"]] = {"kind": f["kind"], "wave": f["wave"], "sha256": list(f.get("sha256", []))}
        self.paths = [dict(p) for p in data.get("paths", [])]
        self.markers = [dict(m) for m in data.get("markers", [])]

    def package_wave(self, ecosystem, name, version):
        """Wave id if name@version is a known compromised release, else None."""
        return self.packages.get((ecosystem, normalize_name(ecosystem, name)), {}).get(version.strip())


def validate(data):
    """Return a list of human-readable errors; empty means valid."""
    errors = []
    if not isinstance(data, dict):
        return ["indicator file must be a JSON object"]
    for key in ("version", "waves", "packages", "files", "paths", "markers"):
        if key not in data:
            errors.append("missing top-level key: %s" % key)
    if errors:
        return errors
    waves = data["waves"]
    if not isinstance(waves, dict):
        return ["waves must be an object keyed by wave id"]
    for wid, w in waves.items():
        if not w.get("name"):
            errors.append("wave %s: missing name" % wid)
        if not w.get("references"):
            errors.append("wave %s: needs at least one reference" % wid)

    def check_wave(where, wid):
        if wid not in waves:
            errors.append("%s: unknown wave %r" % (where, wid))

    for i, p in enumerate(data["packages"]):
        where = "packages[%d] %s" % (i, p.get("name", "?"))
        if p.get("ecosystem") not in ECOSYSTEMS:
            errors.append("%s: ecosystem must be one of %s" % (where, ", ".join(ECOSYSTEMS)))
        if not p.get("name"):
            errors.append("%s: missing name" % where)
        if not p.get("versions"):
            errors.append("%s: versions must be a non-empty list" % where)
        check_wave(where, p.get("wave"))
    for i, f in enumerate(data["files"]):
        where = "files[%d] %s" % (i, f.get("name", "?"))
        if not f.get("name") or "/" in f.get("name", ""):
            errors.append("%s: name must be a bare file name" % where)
        if f.get("kind") not in FILE_KINDS:
            errors.append("%s: kind must be one of %s" % (where, ", ".join(FILE_KINDS)))
        if not isinstance(f.get("sha256"), list) or any(not _SHA256.match(h) for h in f.get("sha256", [])):
            errors.append("%s: sha256 must be a list of lowercase hex digests" % where)
        check_wave(where, f.get("wave"))
    for i, p in enumerate(data["paths"]):
        where = "paths[%d] %s" % (i, p.get("pattern", "?"))
        if not p.get("pattern") or p["pattern"].startswith("/"):
            errors.append("%s: pattern must be a relative path glob" % where)
        check_wave(where, p.get("wave"))
    for i, m in enumerate(data["markers"]):
        where = "markers[%d]" % i
        if len(m.get("text", "")) < 6:
            errors.append("%s: marker text must be at least 6 characters" % where)
        check_wave(where, m.get("wave"))
    return errors


def resolve_path(path=None):
    """Explicit path > $SHAI_HULUD_IOCS > committed file."""
    if path:
        return Path(path)
    env = os.environ.get("SHAI_HULUD_IOCS")
    if env:
        return Path(env)
    return DEFAULT_IOCS


def load(path=None):
    """Load, validate and index the indicator file. Raises ValueError when invalid."""
    p = resolve_path(path)
    with open(p, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    errors = validate(data)
    if errors:
        raise ValueError("invalid indicator file %s:\n  %s" % (p, "\n  ".join(errors)))
    return Iocs(data)


class AllowRule(object):
    def __init__(self, command, packages=None):
        self.pattern = re.compile(command)
        self.packages = set(packages or [])

    def matches(self, command, package_name):
        if self.packages and package_name not in self.packages:
            return False
        return bool(self.pattern.match(command.strip()))


def load_allowlist(path=None):
    with open(path or DEFAULT_ALLOWLIST, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    return [AllowRule(e["command"], e.get("packages")) for e in data.get("entries", [])]


def is_allowed(rules, command, package_name):
    return any(r.matches(command, package_name) for r in rules)
