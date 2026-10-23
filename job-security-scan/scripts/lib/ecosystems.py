"""ecosystems.py - ecosystem descriptors and repository auto-detection.

Stdlib only; compatible with Python 3.8+.

An ecosystem is described by one JSON file in ecosystems/. Adding support for a new
language needs only a new descriptor - no scanner code changes. The scanner asks
detect() which ecosystems a repository uses, which lockfiles OSV-Scanner should read
and which Semgrep rulesets apply.
"""

import fnmatch
import json
import os
import re

SUPPORTED_SCHEMA = 1

# Directories that hold third-party or generated code, never the project's own manifests.
SKIP_DIRS = frozenset([
    ".git", ".hg", ".svn", "node_modules", "vendor", "target", "build", "dist", "out",
    ".gradle", ".next", ".nuxt", ".venv", "venv", "env", "__pycache__", ".tox", ".mypy_cache",
    ".idea", ".vscode", "obj", "bin", ".terraform", ".security-scan-results", "site-packages",
])

DEFAULT_MAX_DEPTH = 4

_ID_RE = re.compile(r"[a-z][a-z0-9-]*")
_SEMGREP_RE = re.compile(r"(p|r)/[A-Za-z0-9_.-]+|[./~]\S+|https://\S+")
_KNOWN_KEYS = {"schema_version", "id", "name", "detect", "lockfiles", "osv_ecosystem",
               "runtime", "semgrep", "docker"}


class EcosystemError(Exception):
    """Raised for unreadable or invalid descriptors."""


def default_dir():
    return os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "ecosystems")


# ------------------------------------------------------------------ descriptors

def _str_list(value, label, errors, allow_empty=False):
    if not isinstance(value, list) or (not value and not allow_empty):
        errors.append("%s: must be a non-empty list of strings" % label)
        return []
    out = []
    for i, item in enumerate(value):
        if not isinstance(item, str) or not item or "/" in item and label in ("detect", "lockfiles"):
            errors.append("%s[%d]: must be a non-empty string%s" % (
                label, i, " without '/' (patterns match file names)" if label in ("detect", "lockfiles") else ""))
        else:
            out.append(item)
    return out


def validate_descriptor(d):
    """Return a list of error strings for one parsed descriptor."""
    errors = []
    if not isinstance(d, dict):
        return ["descriptor must be a JSON object"]
    for key in d:
        if key not in _KNOWN_KEYS:
            errors.append("unknown field '%s'" % key)
    if type(d.get("schema_version")) is not int or d.get("schema_version") != SUPPORTED_SCHEMA:
        errors.append("schema_version: must be %d" % SUPPORTED_SCHEMA)
    if not isinstance(d.get("id"), str) or not _ID_RE.fullmatch(d.get("id", "")):
        errors.append("id: must be lowercase kebab-case")
    if not isinstance(d.get("name"), str) or not d.get("name"):
        errors.append("name: required")
    _str_list(d.get("detect"), "detect", errors)
    _str_list(d.get("lockfiles", []), "lockfiles", errors, allow_empty=True)
    if not isinstance(d.get("osv_ecosystem"), str) or not d.get("osv_ecosystem"):
        errors.append("osv_ecosystem: required (OSV ecosystem name, e.g. 'npm', 'PyPI', 'Maven')")
    if "semgrep" in d:
        for i, r in enumerate(_str_list(d["semgrep"], "semgrep", errors, allow_empty=True)):
            if not _SEMGREP_RE.fullmatch(r):
                errors.append("semgrep[%d]: %r is not a registry ruleset like 'p/python'" % (i, r))
    if "docker" in d:
        dk = d["docker"]
        if not isinstance(dk, dict) or set(dk) - {"images"}:
            errors.append("docker: must be an object with only 'images'")
        else:
            _str_list(dk.get("images", []), "docker.images", errors, allow_empty=True)
    if "runtime" in d:
        rt = d["runtime"]
        if not isinstance(rt, dict) or set(rt) - {"name", "extractors", "eol_product"}:
            errors.append("runtime: must be an object with name, extractors, eol_product")
        else:
            if not isinstance(rt.get("name"), str) or not rt.get("name"):
                errors.append("runtime.name: required")
            if "eol_product" in rt and not isinstance(rt["eol_product"], str):
                errors.append("runtime.eol_product: must be a string")
            exts = rt.get("extractors", [])
            if not isinstance(exts, list):
                errors.append("runtime.extractors: must be a list")
            else:
                for i, e in enumerate(exts):
                    where = "runtime.extractors[%d]" % i
                    if not isinstance(e, dict) or "file" not in e or ("regex" in e) == ("json_path" in e) \
                            or set(e) - {"file", "regex", "json_path"}:
                        errors.append("%s: needs 'file' and exactly one of 'regex' or 'json_path'" % where)
                        continue
                    if "regex" in e:
                        try:
                            if re.compile(e["regex"]).groups < 1:
                                errors.append("%s.regex: needs one capture group for the version" % where)
                        except re.error as exc:
                            errors.append("%s.regex: invalid (%s)" % (where, exc))
    return errors


def load_descriptors(directory=None):
    """Load and validate every *.json in the directory. Raises EcosystemError on any problem."""
    directory = directory or default_dir()
    if not os.path.isdir(directory):
        raise EcosystemError("ecosystems directory not found: %s" % directory)
    result, problems, seen = [], [], {}
    for name in sorted(os.listdir(directory)):
        if not name.endswith(".json"):
            continue
        path = os.path.join(directory, name)
        try:
            with open(path, "r", encoding="utf-8") as fh:
                d = json.load(fh)
        except (OSError, ValueError) as exc:
            problems.append("%s: %s" % (name, exc))
            continue
        errs = validate_descriptor(d)
        if not errs and d["id"] != name[:-5]:
            errs.append("id '%s' must match the file name '%s'" % (d["id"], name))
        if not errs and d["id"] in seen:
            errs.append("duplicate id '%s'" % d["id"])
        if errs:
            problems.extend("%s: %s" % (name, e) for e in errs)
            continue
        seen[d["id"]] = name
        result.append(d)
    if problems:
        raise EcosystemError("\n".join(problems))
    if not result:
        raise EcosystemError("no ecosystem descriptors found in %s" % directory)
    return result


# -------------------------------------------------------------------- detection

def _matches(name, patterns):
    return any(fnmatch.fnmatchcase(name, p) for p in patterns)


def detect(path, descriptors, max_depth=DEFAULT_MAX_DEPTH):
    """Detect which ecosystems a repository uses.

    Returns a dict:
      path, ecosystems[{id, name, osv_ecosystem, manifests[], lockfiles[], semgrep[],
                        docker_images[], needs_sbom}],
      lockfiles[]   every scannable lockfile (relative paths, sorted, de-duplicated),
      semgrep[]     union of ruleset ids,
      needs_sbom    True when nothing was recognised or an ecosystem has no lockfile.
    """
    if not os.path.isdir(path):
        raise EcosystemError("not a directory: %s" % path)
    root = os.path.abspath(path)
    found = {d["id"]: {"manifests": [], "lockfiles": []} for d in descriptors}

    for dirpath, dirnames, filenames in os.walk(root):
        depth = 0 if dirpath == root else os.path.relpath(dirpath, root).count(os.sep) + 1
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".git"))
        if depth >= max_depth:
            dirnames[:] = []
        for fname in sorted(filenames):
            rel = os.path.relpath(os.path.join(dirpath, fname), root).replace(os.sep, "/")
            for d in descriptors:
                if _matches(fname, d["detect"]):
                    found[d["id"]]["manifests"].append(rel)
                if _matches(fname, d.get("lockfiles", [])):
                    found[d["id"]]["lockfiles"].append(rel)

    ecosystems, all_locks, all_semgrep = [], set(), set()
    for d in descriptors:
        f = found[d["id"]]
        if not f["manifests"] and not f["lockfiles"]:
            continue
        ecosystems.append({
            "id": d["id"], "name": d["name"], "osv_ecosystem": d["osv_ecosystem"],
            "manifests": f["manifests"], "lockfiles": f["lockfiles"],
            "semgrep": list(d.get("semgrep", [])),
            "docker_images": list(d.get("docker", {}).get("images", [])),
            "needs_sbom": not f["lockfiles"],
        })
        all_locks.update(f["lockfiles"])
        all_semgrep.update(d.get("semgrep", []))

    return {
        "path": root,
        "ecosystems": ecosystems,
        "lockfiles": sorted(all_locks),
        "semgrep": sorted(all_semgrep),
        "needs_sbom": (not ecosystems) or any(e["needs_sbom"] for e in ecosystems),
    }
