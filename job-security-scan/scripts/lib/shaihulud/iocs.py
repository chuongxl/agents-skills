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


def merge(base, extra):
    """Union of two indicator files. The extra file can only ADD indicators, never remove or weaken one."""
    out = json.loads(json.dumps(base))
    if extra.get("version"):
        out["version"] = "%s+%s" % (base.get("version", ""), extra["version"])
    for wid, w in (extra.get("waves") or {}).items():
        out["waves"].setdefault(wid, w)
    index = dict(((p.get("ecosystem"), normalize_name(p.get("ecosystem", ""), p.get("name", ""))), p)
                 for p in out["packages"] if isinstance(p, dict))
    for p in extra.get("packages", []):
        if not isinstance(p, dict):
            continue
        key = (p.get("ecosystem"), normalize_name(p.get("ecosystem", ""), p.get("name", "")))
        if key in index:
            have = index[key].setdefault("versions", [])
            have.extend(v for v in p.get("versions", []) if v not in have)
        else:
            out["packages"].append(json.loads(json.dumps(p)))
            index[key] = out["packages"][-1]
    by_name = dict((f.get("name"), f) for f in out["files"] if isinstance(f, dict))
    for f in extra.get("files", []):
        if not isinstance(f, dict):
            continue
        if f.get("name") in by_name:        # same payload name: keep the committed entry, add any new hashes
            have = by_name[f["name"]].setdefault("sha256", [])
            have.extend(h for h in f.get("sha256", []) if h not in have)
        else:
            out["files"].append(json.loads(json.dumps(f)))
            by_name[f.get("name")] = out["files"][-1]
    for section, ident in (("paths", "pattern"), ("markers", "text")):
        seen = set(i.get(ident) for i in out[section] if isinstance(i, dict))
        out[section].extend(i for i in extra.get(section, []) if isinstance(i, dict) and i.get(ident) not in seen)
    return out


def load(path=None):
    """Load, validate and index the indicators: the committed file always, plus (merged on top) an explicit file,
    $SHAI_HULUD_IOCS or the refreshed cache. Extra files can add indicators but never replace or drop the
    committed ones, so a stale, truncated or tampered cache cannot blind the check. Raises ValueError when invalid."""
    p = resolve_path(path)
    with open(str(DEFAULT_IOCS), "r", encoding="utf-8") as fh:
        data = json.load(fh)
    if os.path.realpath(str(p)) != os.path.realpath(str(DEFAULT_IOCS)):
        with open(p, "r", encoding="utf-8") as fh:
            extra = json.load(fh)
        if not isinstance(extra, dict):
            raise ValueError("invalid indicator file %s: must be a JSON object" % p)
        errors = validate(extra)            # the extra file must be a complete, valid indicator file on its own
        if errors:
            raise ValueError("invalid indicator file %s:\n  %s" % (p, "\n  ".join(errors)))
        merged = merge(data, extra)
        errors = validate(merged)
        if errors:
            raise ValueError("invalid indicator file %s:\n  %s" % (p, "\n  ".join(errors)))
        data = merged
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


_SEGMENTS = re.compile(r"\s*(?:&&|\|\||;|\||&)\s*")


def is_allowed(rules, command, package_name):
    """True only when every segment of a chained command (&&, ||, ;, |, &) is allowlisted, so
    'husky && node evil.js' is not waved through by its benign prefix."""
    segments = [seg for seg in _SEGMENTS.split(command.strip()) if seg]
    return bool(segments) and all(any(r.matches(seg, package_name) for r in rules) for seg in segments)
