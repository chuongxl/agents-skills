"""advisory.py - load and validate advisory bundles.

Stdlib only; compatible with Python 3.8+.

Two layers of checking:
  1. Structural: a small JSON-Schema subset validator driven by
     assets/advisory.schema.json, so the schema file is the single source of truth.
  2. Semantic: rules a schema cannot express (trusted hosts, fixed versions on
     published advisories, version ordering, approval of LLM-assisted data, ids).
"""

import json
import os
import re
from urllib.parse import urlparse


class AdvisoryError(Exception):
    """Raised for unreadable files or malformed JSON."""


# ---------------------------------------------------------------- JSON loading

def load_json(path):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except OSError as exc:
        raise AdvisoryError("cannot read %s: %s" % (path, exc))
    except ValueError as exc:
        raise AdvisoryError("invalid JSON in %s: %s" % (path, exc))


# ------------------------------------------------------- JSON-Schema subset

_TYPES = {
    "object": lambda v: isinstance(v, dict),
    "array": lambda v: isinstance(v, list),
    "string": lambda v: isinstance(v, str),
    "boolean": lambda v: isinstance(v, bool),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
}


def _resolve_ref(ref, root):
    if not ref.startswith("#/"):
        raise AdvisoryError("unsupported $ref %r (only local '#/...' refs)" % (ref,))
    node = root
    for part in ref[2:].split("/"):
        if not isinstance(node, dict) or part not in node:
            raise AdvisoryError("unresolvable $ref %r" % (ref,))
        node = node[part]
    return node


def _strict_end(pattern):
    # Python's '$' also matches before a trailing newline; JSON Schema's does not.
    return re.sub(r"(?<!\\)\$$", r"\\Z", pattern)


def validate_schema(instance, schema, root=None, path="$"):
    """Return a list of error strings; empty list means valid."""
    root = root if root is not None else schema
    errors = []

    if "$ref" in schema:
        return validate_schema(instance, _resolve_ref(schema["$ref"], root), root, path)

    if "const" in schema and (instance != schema["const"] or type(instance) is not type(schema["const"])):
        errors.append("%s: must be %r" % (path, schema["const"]))
        return errors

    if "enum" in schema and instance not in schema["enum"]:
        errors.append("%s: %r is not one of %s" % (path, instance, ", ".join(map(repr, schema["enum"]))))
        return errors

    stype = schema.get("type")
    if stype is not None:
        check = _TYPES.get(stype)
        if check is None:
            raise AdvisoryError("unsupported schema type %r" % (stype,))
        if not check(instance):
            errors.append("%s: expected %s, got %s" % (path, stype, type(instance).__name__))
            return errors

    if isinstance(instance, str):
        if "minLength" in schema and len(instance) < schema["minLength"]:
            errors.append("%s: shorter than %d characters" % (path, schema["minLength"]))
        if "pattern" in schema and not re.search(_strict_end(schema["pattern"]), instance):
            errors.append("%s: %r does not match pattern %s" % (path, instance, schema["pattern"]))

    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        if "minimum" in schema and instance < schema["minimum"]:
            errors.append("%s: %s is below minimum %s" % (path, instance, schema["minimum"]))
        if "maximum" in schema and instance > schema["maximum"]:
            errors.append("%s: %s is above maximum %s" % (path, instance, schema["maximum"]))

    if isinstance(instance, list):
        if "minItems" in schema and len(instance) < schema["minItems"]:
            errors.append("%s: needs at least %d item(s)" % (path, schema["minItems"]))
        if "items" in schema:
            for i, item in enumerate(instance):
                errors.extend(validate_schema(item, schema["items"], root, "%s[%d]" % (path, i)))

    if isinstance(instance, dict):
        props = schema.get("properties", {})
        for name in schema.get("required", []):
            if name not in instance:
                errors.append("%s: missing required field '%s'" % (path, name))
        if schema.get("additionalProperties") is False:
            for name in instance:
                if name not in props:
                    errors.append("%s: unknown field '%s'" % (path, name))
        for name, sub in props.items():
            if name in instance:
                errors.extend(validate_schema(instance[name], sub, root, "%s.%s" % (path, name)))

    return errors


# ------------------------------------------------------------ semantic checks

_VERSION_RE = re.compile(r"^\d+(\.\d+)*$")


def _vtuple(version):
    """Numeric version tuple, or None when the version is not plain dotted numbers."""
    if isinstance(version, str) and _VERSION_RE.match(version):
        return tuple(int(p) for p in version.split("."))
    return None


def _pad(a, b):
    n = max(len(a), len(b))
    return a + (0,) * (n - len(a)), b + (0,) * (n - len(b))


def host_of(url):
    return (urlparse(url).hostname or "").lower()


def semantic_checks(adv, where, allowed_hosts=None, strict=False):
    """Return (errors, warnings) for one structurally valid advisory."""
    errors, warnings = [], []
    aid = adv.get("id", "?")
    tag = "%s [%s]" % (where, aid)

    if aid in adv.get("aliases", []):
        errors.append("%s: aliases must not repeat the id" % tag)

    src = adv.get("source", {})
    url = src.get("url", "")
    if allowed_hosts is not None and url:
        if host_of(url) not in allowed_hosts:
            errors.append("%s: source host '%s' is not in the allowed_hosts of sources.json" % (tag, host_of(url)))

    if src.get("method") == "llm-assisted" and not src.get("approved_by"):
        msg = "%s: llm-assisted data has no source.approved_by (a human must approve it before the engine trusts it)" % tag
        (errors if strict else warnings).append(msg)

    for i, aff in enumerate(adv.get("affected", [])):
        loc = "%s affected[%d]" % (tag, i)
        if adv.get("status") == "published" and not (aff.get("fixed") or aff.get("last_affected")):
            errors.append("%s: published advisory needs 'fixed' or 'last_affected'" % loc)
        intro, fixed = _vtuple(aff.get("introduced")), _vtuple(aff.get("fixed"))
        if intro is not None and fixed is not None:
            a, b = _pad(intro, fixed)
            if a >= b:
                errors.append("%s: fixed %s is not after introduced %s" % (loc, aff.get("fixed"), aff.get("introduced")))
        last = _vtuple(aff.get("last_affected"))
        if intro is not None and last is not None:
            a, b = _pad(intro, last)
            if a > b:
                errors.append("%s: last_affected %s is before introduced %s" % (loc, aff.get("last_affected"), aff.get("introduced")))

    return errors, warnings


# ------------------------------------------------------------------ file level

def iter_advisory_files(paths):
    """Expand files/directories into a sorted list of .json files."""
    found = []
    for p in paths:
        if os.path.isdir(p):
            for dirpath, _dirs, files in os.walk(p):
                for name in files:
                    if name.endswith(".json"):
                        found.append(os.path.join(dirpath, name))
        elif os.path.isfile(p):
            found.append(p)
        else:
            raise AdvisoryError("path does not exist: %s" % p)
    return sorted(found)


def _collapse(warnings):
    """Report the same warning kind once per file with a count instead of N lines."""
    groups = {}
    for w in warnings:
        kind = w.split("]: ", 1)[-1]
        groups.setdefault(kind, []).append(w)
    out = []
    for kind, items in groups.items():
        out.append(items[0] if len(items) == 1 else "%s: %s (%d advisories affected)" % (items[0].split(" [", 1)[0], kind, len(items)))
    return out


def validate_file(path, schema, allowed_hosts=None, strict=False):
    """Validate one bundle file. Returns dict with errors, warnings, ids."""
    result = {"file": path, "errors": [], "warnings": [], "ids": []}
    try:
        data = load_json(path)
    except AdvisoryError as exc:
        result["errors"].append(str(exc))
        return result

    structural = validate_schema(data, schema)
    result["errors"].extend("%s: %s" % (path, e) for e in structural)
    if structural:
        return result  # semantic checks assume a structurally valid bundle

    seen = set()
    for adv in data["advisories"]:
        aid = adv["id"]
        if aid in seen:
            result["errors"].append("%s: duplicate id '%s' inside the bundle" % (path, aid))
        seen.add(aid)
        errs, warns = semantic_checks(adv, path, allowed_hosts, strict)
        result["errors"].extend(errs)
        result["warnings"].extend(warns)
    result["warnings"] = _collapse(result["warnings"])
    result["ids"] = sorted(seen)
    return result


def validate_paths(paths, schema, allowed_hosts=None, strict=False):
    """Validate many files and check ids are unique across all of them."""
    files = iter_advisory_files(paths)
    results = [validate_file(f, schema, allowed_hosts, strict) for f in files]
    owner = {}
    for r in results:
        for aid in r["ids"]:
            if aid in owner and owner[aid] != r["file"]:
                r["errors"].append("%s: id '%s' is also defined in %s" % (r["file"], aid, owner[aid]))
            else:
                owner.setdefault(aid, r["file"])
    return results
