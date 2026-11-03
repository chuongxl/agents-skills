"""Deep-audit contracts: findings.json and coverage-ledger.json validation, canonical coverage IDs.

A stdlib-only Python port of the validate-findings.cjs and validate-coverage-ledger.cjs validators of
cloudflare/security-audit-skill (MIT, see references/audit/LICENSE-cloudflare.txt), so the deep-audit
phase needs no Node.js. findings.json is checked against assets/audit/findings.schema.json (the upstream
report-schema.json, unchanged) by a small interpreter for the keywords that schema uses, then against
the same semantic rules upstream enforces. Python 3.8+.
"""
import json
import os
import re
import sys
import unicodedata

LIMITS = {
    "input_bytes": 5 * 1024 * 1024,
    "findings": 1000,
    "units": 10000,
    "collection_items": 1000,
    "nesting_depth": 64,
    "errors": 100,
}
MAX_TEXT = 4096
FINGERPRINT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/@+-]*$")
AGENT_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
WINDOWS_RESERVED_AGENT = re.compile(r"^(?:con|prn|aux|nul|com[1-9]|lpt[1-9])$")
WINDOWS_RESERVED_COMPONENT = re.compile(
    "^(?:con|prn|aux|nul|clock\\$|conin\\$|conout\\$|com[1-9¹²³]|lpt[1-9¹²³])(?:\\.|$)",
    re.IGNORECASE)
SEVERITY_RANK = {"informational": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}
SUPPORTED_KEYWORDS = {"$comment", "description", "type", "properties", "required", "additionalProperties",
                      "items", "enum", "const", "minItems", "minLength", "minimum", "pattern", "uniqueItems",
                      "visibleContent", "oneOf"}

LEDGER_FIELDS = ["coverage_id", "canonical_refs", "surface", "boundary", "subsystem", "attack_class",
                 "starting_paths", "ordinary_attack_class_block", "selected_companion_blocks", "excluded_blocks",
                 "prior_status", "attempts", "wave", "status", "agent_id", "reviewed_paths", "local_checks",
                 "result_fingerprints", "unresolved"]
REF_FIELDS = ["surface", "boundary", "subsystem", "attack_class"]
STATUSES = {"planned", "not_applicable", "out_of_scope", "in_progress", "covered", "candidate", "blocked",
            "deferred"}
ATTEMPT_STATUSES = {"covered", "candidate", "blocked"}
ATTEMPT_FIELDS = ["wave", "status", "agent_id", "reviewed_paths", "local_checks", "result_fingerprints",
                  "unresolved", "reassignment_reason"]
PRIOR_STATUSES = {"new", "prior_confirmed_same_source", "prior_confirmed_changed_source", "prior_needs_validation",
                  "prior_deferred", "prior_blocked", "prior_out_of_scope", "prior_covered_same_source",
                  "prior_covered_changed_source", "prior_rejected_claim_changed", "none"}
QUICK_SUBSYSTEM = "profile/quick/all-in-scope-subsystems"

SCHEMA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "assets", "audit",
                           "findings.schema.json")

# Unicode Default_Ignorable_Code_Point outside the Cf category (Cf is excluded separately).
_DEFAULT_IGNORABLE = ((0x034F, 0x034F), (0x115F, 0x1160), (0x17B4, 0x17B5), (0x180B, 0x180F),
                      (0x3164, 0x3164), (0xFE00, 0xFE0F), (0xFFA0, 0xFFA0), (0xFFF0, 0xFFF8),
                      (0x1BCA0, 0x1BCA3), (0x1D173, 0x1D17A), (0xE0000, 0xE0FFF))


def _list(value):
    return value if isinstance(value, list) else []


def _in(value, collection):
    """Membership that never raises on unhashable (list/dict) input."""
    return isinstance(value, str) and value in collection


class AuditInputError(Exception):
    """Input that cannot be validated at all (too large, not JSON, too deep)."""


def _ignorable(ch):
    cp = ord(ch)
    return any(lo <= cp <= hi for lo, hi in _DEFAULT_IGNORABLE)


def _valid_scalars(value):
    return not any(0xD800 <= ord(ch) <= 0xDFFF for ch in value)


def visible(value):
    """True when the string holds at least one visible character (upstream VISIBLE_CONTENT)."""
    if not isinstance(value, str) or not _valid_scalars(value):
        return False
    for ch in value:
        if ch.isspace() or unicodedata.category(ch) in ("Cc", "Cf") or _ignorable(ch):
            continue
        return True
    return False


def _forbidden_path_char(value):
    return any(unicodedata.category(ch) in ("Cc", "Cf", "Zl", "Zp") or _ignorable(ch) for ch in value)


def visible_text(value, max_length=MAX_TEXT):
    return (isinstance(value, str) and 0 < len(value) <= max_length and value.strip() == value
            and visible(value))


def safe_relative_path(value):
    if (not isinstance(value, str) or not value or not _valid_scalars(value) or value.strip() != value
            or _forbidden_path_char(value) or "\\" in value or ":" in value):
        return False
    if value.startswith("/") or value.startswith("~") or re.match(r"^[A-Za-z]:", value):
        return False
    for seg in value.split("/"):
        if seg in ("", ".", "..") or seg[-1] in " ." or WINDOWS_RESERVED_COMPONENT.match(seg):
            return False
    return True


def safe_agent_id(value):
    return isinstance(value, str) and bool(AGENT_ID_RE.match(value)) and not WINDOWS_RESERVED_AGENT.match(value)


def safe_fingerprint(value):
    return isinstance(value, str) and bool(FINGERPRINT_RE.match(value))


# ── canonical coverage IDs ────────────────────────────────────────────────────

def canonical_ref(value):
    return (visible_text(value, 1024) and not _forbidden_path_char(value)
            and unicodedata.normalize("NFC", value) == value)


def encode_ref(value):
    if not canonical_ref(value):
        raise ValueError("invalid canonical reference: %r" % (value,))
    out = []
    for byte in value.encode("utf-8"):
        c = chr(byte)
        out.append(c if (c.isascii() and (c.isalnum() or c in "-._~")) else "%%%02X" % byte)
    return "".join(out)


def coverage_id(refs):
    """surface::boundary::subsystem::attack_class[::lifecycle], each RFC 3986 percent-encoded."""
    if not isinstance(refs, dict):
        raise ValueError("canonical_refs must be an object")
    fields = REF_FIELDS + (["lifecycle"] if "lifecycle" in refs else [])
    if set(refs) != set(fields):
        raise ValueError("canonical_refs has missing or unexpected fields")
    return "::".join(encode_ref(refs[f]) for f in fields)


# ── safe loading ──────────────────────────────────────────────────────────────

def _depth(value, limit):
    stack = [(value, 1)]
    while stack:
        item, d = stack.pop()
        if d > limit:
            return False
        if isinstance(item, dict):
            stack.extend((v, d + 1) for v in item.values())
        elif isinstance(item, list):
            stack.extend((v, d + 1) for v in item)
    return True


def load_json(path):
    try:
        size = os.path.getsize(path)
    except OSError as exc:
        raise AuditInputError("%s: cannot read: %s" % (path, exc))
    if size > LIMITS["input_bytes"]:
        raise AuditInputError("%s: exceeds %d byte limit" % (path, LIMITS["input_bytes"]))
    try:
        with open(path, "rb") as fh:
            text = fh.read(LIMITS["input_bytes"] + 1).decode("utf-8")
        data = json.loads(text, parse_constant=lambda c: (_ for _ in ()).throw(ValueError("non-finite " + c)))
    except (UnicodeDecodeError, ValueError) as exc:
        raise AuditInputError("%s: invalid JSON: %s" % (path, exc))
    if not _depth(data, LIMITS["nesting_depth"]):
        raise AuditInputError("%s: exceeds nesting depth limit %d" % (path, LIMITS["nesting_depth"]))
    return data


# ── schema interpreter (the subset report-schema.json uses) ───────────────────

def _type_of(value):
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    return "object" if isinstance(value, dict) else type(value).__name__


def _type_ok(value, expected):
    actual = _type_of(value)
    return actual == expected or (expected == "number" and actual == "integer")


def _canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def check_schema(schema, p="schema"):
    """Refuse a schema that uses keywords this interpreter would silently ignore."""
    errors = []
    if not isinstance(schema, dict):
        return ["%s: schema must be an object" % p]
    for key in schema:
        if key not in SUPPORTED_KEYWORDS:
            errors.append("%s: unsupported schema keyword %r" % (p, key))
    for key, sub in (schema.get("properties") or {}).items():
        errors += check_schema(sub, "%s.properties.%s" % (p, key))
    if "items" in schema:
        errors += check_schema(schema["items"], p + ".items")
    for i, branch in enumerate(schema.get("oneOf") or []):
        errors += check_schema(branch, "%s.oneOf[%d]" % (p, i))
    return errors


def _validate(value, schema, p, errors):
    if "oneOf" in schema:
        results = []
        for branch in schema["oneOf"]:
            branch_errors = []
            _validate(value, branch, p, branch_errors)
            results.append(branch_errors)
        passing = [i for i, r in enumerate(results) if not r]
        if len(passing) != 1:
            errors.append("%s: must match exactly one schema in oneOf; matched %d" % (p, len(passing)))
            if not passing and isinstance(value, dict):
                matches = [i for i, b in enumerate(schema["oneOf"])
                           for k, s in (b.get("properties") or {}).items()
                           if isinstance(s, dict) and "const" in s and value.get(k, object()) == s["const"]]
                if len(matches) == 1:
                    errors.extend(results[matches[0]])
    if "const" in schema and value != schema["const"]:
        errors.append("%s: must equal %r, got %r" % (p, schema["const"], value))
        return
    if "enum" in schema and value not in schema["enum"]:
        errors.append("%s: invalid value %r (expected one of %s)" % (p, value, ", ".join(map(str, schema["enum"]))))
        return
    if "type" in schema and not _type_ok(value, schema["type"]):
        errors.append("%s: expected %s, got %s" % (p, schema["type"], _type_of(value)))
        return
    if isinstance(value, dict):
        props = schema.get("properties") or {}
        for req in schema.get("required", []):
            if req not in value:
                errors.append("%s: missing required field %r" % (p, req))
        for key, item in value.items():
            if key in props:
                _validate(item, props[key], "%s.%s" % (p, key), errors)
            elif schema.get("additionalProperties") is False:
                errors.append("%s: unexpected field %r" % (p, key))
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            errors.append("%s: must have at least %d item(s), got %d" % (p, schema["minItems"], len(value)))
        seen = set()
        for i, item in enumerate(value):
            if "items" in schema:
                _validate(item, schema["items"], "%s[%d]" % (p, i), errors)
            if schema.get("uniqueItems"):
                key = _canonical(item)
                if key in seen:
                    errors.append("%s: items must be unique; duplicate at index %d" % (p, i))
                seen.add(key)
    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0):
            errors.append("%s: must have at least %d character(s)" % (p, schema["minLength"]))
        if schema.get("visibleContent"):
            if not _valid_scalars(value):
                errors.append("%s: must contain only valid Unicode scalar values" % p)
            elif not visible(value):
                errors.append("%s: must contain a visible character" % p)
        if "pattern" in schema and not re.search(schema["pattern"], value):
            errors.append("%s: must match pattern %s" % (p, json.dumps(schema["pattern"])))
    if "minimum" in schema and _type_of(value) in ("integer", "number") and value < schema["minimum"]:
        errors.append("%s: must be at least %s, got %s" % (p, schema["minimum"], value))


def load_schema(path=SCHEMA_PATH):
    with open(path, encoding="utf-8") as fh:
        schema = json.load(fh)
    problems = check_schema(schema)
    if problems:
        raise AuditInputError("schema %s: %s" % (path, "; ".join(problems)))
    return schema


# ── findings.json ─────────────────────────────────────────────────────────────

def _trace_kind_errors(finding, base):
    errors = []
    trace = finding.get("trace")
    if not isinstance(trace, list) or not trace:
        return errors
    kinds = [t.get("kind") if isinstance(t, dict) else None for t in trace]
    if len(kinds) == 1:
        if kinds[0] not in ("entrypoint", "sink"):
            errors.append('%s.trace[0].kind: a one-line trace must be "entrypoint" or "sink"' % base)
        return errors
    if kinds[0] != "entrypoint":
        errors.append('%s.trace[0].kind: must be "entrypoint", got %r' % (base, kinds[0]))
    if kinds[-1] != "sink":
        errors.append('%s.trace[%d].kind: must be "sink", got %r' % (base, len(kinds) - 1, kinds[-1]))
    for i in range(1, len(kinds) - 1):
        if kinds[i] != "propagation":
            errors.append('%s.trace[%d].kind: must be "propagation", got %r' % (base, i, kinds[i]))
    return errors


def finding_semantic_errors(findings):
    errors = []
    if not isinstance(findings, list):
        return errors
    seen = {}
    previous = None
    for index, finding in enumerate(findings):
        if not isinstance(finding, dict):
            continue
        base = "$[%d]" % index
        fp = finding.get("fingerprint")
        if isinstance(fp, str):
            if fp in seen:
                errors.append("%s.fingerprint: duplicate of $[%d].fingerprint" % (base, seen[fp]))
            else:
                seen[fp] = index
            if previous is not None and previous > fp:
                errors.append("%s.fingerprint: findings must be sorted lexicographically" % base)
            previous = fp
        for field in ("trace", "evidence"):
            for i, entry in enumerate(_list(finding.get(field))):
                if not isinstance(entry, dict):
                    continue
                if "line" in entry and (_type_of(entry["line"]) != "integer" or entry["line"] < 1):
                    errors.append("%s.%s[%d].line: must be a positive integer" % (base, field, i))
                if "file" in entry and not safe_relative_path(entry["file"]):
                    errors.append("%s.%s[%d].file: must be a safe repository-relative source path" % (base, field, i))
        remediation = finding.get("remediation")
        if isinstance(remediation, dict):
            for i, change in enumerate(_list(remediation.get("code_changes"))):
                if isinstance(change, dict) and "file_name" in change and not safe_relative_path(change["file_name"]):
                    errors.append("%s.remediation.code_changes[%d].file_name: must be a safe repository-relative "
                                  "source path" % (base, i))
        errors += _trace_kind_errors(finding, base)
        verdict = finding.get("verdict")
        if verdict == "confirmed":
            for bad in ("claimed_root_cause", "blockers", "validation_plan", "reason"):
                if bad in finding:
                    errors.append("%s: confirmed finding must not contain %r" % (base, bad))
            execution = finding.get("execution")
            if not isinstance(execution, dict) or not visible(execution.get("observed_result")):
                errors.append("%s: confirmed finding requires a visible execution observed_result" % base)
            if not isinstance(remediation, dict) or not visible(remediation.get("strategy")):
                errors.append("%s: confirmed finding requires visible remediation" % base)
            sev = finding.get("severity") if isinstance(finding.get("severity"), dict) else {}
            overall = sev.get("overall_severity")
            impact = (sev.get("impact") or {}).get("score") if isinstance(sev.get("impact"), dict) else None
            if _in(overall, SEVERITY_RANK) and _in(impact, SEVERITY_RANK) and SEVERITY_RANK[overall] > SEVERITY_RANK[impact]:
                errors.append("%s.severity.overall_severity: cannot exceed demonstrated impact %r" % (base, impact))
        elif verdict == "needs_validation":
            for bad in ("severity", "execution", "remediation", "reason", "root_cause"):
                if bad in finding:
                    errors.append("%s: needs_validation finding must not contain %r" % (base, bad))
            plan = finding.get("validation_plan") if isinstance(finding.get("validation_plan"), dict) else {}
            if not (visible(plan.get("local")) or visible(plan.get("deployment"))):
                errors.append("%s.validation_plan: requires at least one visible local or deployment plan" % base)
        elif verdict == "rejected":
            for bad in ("severity", "execution", "remediation", "blockers", "validation_plan", "root_cause"):
                if bad in finding:
                    errors.append("%s: rejected finding must not contain %r" % (base, bad))
    return errors


def validate_findings(findings, schema=None):
    """Errors (list of str, capped) for a parsed findings.json document."""
    schema = schema or load_schema()
    if isinstance(findings, list) and len(findings) > LIMITS["findings"]:
        return ["$: exceeds %d findings" % LIMITS["findings"]]
    errors = []
    _validate(findings, schema, "$data", errors)
    errors += finding_semantic_errors(findings)
    return errors[:LIMITS["errors"]]


# ── coverage-ledger.json ──────────────────────────────────────────────────────

def _string_list(value, loc, errors, allow_empty=True, path_value=False, fingerprint=False):
    if not isinstance(value, list):
        errors.append("%s: expected array" % loc)
        return
    if not allow_empty and not value:
        errors.append("%s: must not be empty" % loc)
    if len(value) > LIMITS["collection_items"]:
        errors.append("%s: exceeds %d entries" % (loc, LIMITS["collection_items"]))
    seen = set()
    for i, entry in enumerate(value[:LIMITS["collection_items"]]):
        eloc = "%s[%d]" % (loc, i)
        if fingerprint:
            if not safe_fingerprint(entry):
                errors.append("%s: invalid fingerprint" % eloc)
        elif not (safe_relative_path(entry) if path_value else visible_text(entry)):
            errors.append("%s: invalid %s" % (eloc, "repository-relative path" if path_value else "text"))
        if isinstance(entry, str):
            if entry in seen:
                errors.append("%s: duplicate entry" % eloc)
            seen.add(entry)


def _owned_artifact(value, agent_id):
    prefix = "agents/%s/artifacts/" % agent_id
    return (safe_agent_id(agent_id) and safe_relative_path(value) and value.startswith(prefix)
            and len(value) > len(prefix))


def _checks(value, loc, errors):
    if not isinstance(value, list):
        errors.append("%s: expected array" % loc)
        return
    for i, check in enumerate(value[:LIMITS["collection_items"]]):
        base = "%s[%d]" % (loc, i)
        if not isinstance(check, dict):
            errors.append("%s: expected object" % base)
            continue
        for field in ("agent_id", "reviewed_paths", "invariant", "method", "result", "artifact"):
            if field not in check:
                errors.append("%s: missing required field %r" % (base, field))
        if not safe_agent_id(check.get("agent_id")):
            errors.append("%s.agent_id: expected a canonical lowercase agent ID" % base)
        _string_list(check.get("reviewed_paths"), base + ".reviewed_paths", errors, allow_empty=False, path_value=True)
        if not visible_text(check.get("invariant")):
            errors.append("%s.invariant: invalid text" % base)
        method = check.get("method")
        if not _in(method, ("source", "local")):
            errors.append('%s.method: expected "source" or "local"' % base)
        if not visible_text(check.get("result")):
            errors.append("%s.result: invalid text" % base)
        if method == "source" and check.get("artifact") is not None:
            errors.append("%s.artifact: source-only check must use null" % base)
        elif method == "local" and not _owned_artifact(check.get("artifact"), check.get("agent_id")):
            errors.append("%s.artifact: local check requires an artifact owned by agent %r"
                          % (base, check.get("agent_id") if safe_agent_id(check.get("agent_id")) else "<agent-id>"))


def _path_ownership(unit, base, errors):
    if not isinstance(unit.get("reviewed_paths"), list) or not isinstance(unit.get("local_checks"), list):
        return
    aggregate = set(p for p in unit["reviewed_paths"] if isinstance(p, str))
    owned = set()
    for check in unit["local_checks"]:
        if isinstance(check, dict) and isinstance(check.get("reviewed_paths"), list):
            owned.update(p for p in check["reviewed_paths"] if isinstance(p, str))
    for p in sorted(aggregate - owned):
        errors.append("%s.reviewed_paths: %r has no check owner" % (base, p))
    for p in sorted(owned - aggregate):
        errors.append("%s.local_checks: owned path %r is absent from aggregate reviewed_paths" % (base, p))


def _state(unit, base, errors):
    status = unit.get("status")

    def empty(field):
        if isinstance(unit.get(field), list) and unit[field]:
            errors.append("%s.%s: unit with status %r must keep this array empty" % (base, field, status))

    def nonempty(field):
        if not isinstance(unit.get(field), list) or not unit[field]:
            errors.append("%s.%s: unit with status %r requires entries" % (base, field, status))

    def owner():
        if not safe_agent_id(unit.get("agent_id")):
            errors.append("%s.agent_id: unit with status %r requires a canonical lowercase agent ID" % (base, status))

    if status != "candidate":
        empty("result_fingerprints")
    if status == "planned":
        if unit.get("agent_id") is not None:
            errors.append("%s.agent_id: planned unit must be unassigned" % base)
        empty("reviewed_paths"), empty("local_checks"), empty("unresolved")
    elif status in ("not_applicable", "out_of_scope", "deferred"):
        if unit.get("agent_id") is not None:
            errors.append("%s.agent_id: unit with status %r must be unassigned" % (base, status))
        empty("reviewed_paths"), empty("local_checks"), nonempty("unresolved")
    elif status == "in_progress":
        owner(), empty("reviewed_paths"), empty("local_checks"), empty("unresolved")
    elif status == "blocked":
        owner(), nonempty("reviewed_paths"), nonempty("local_checks"), nonempty("unresolved")
    elif status == "covered":
        owner(), nonempty("reviewed_paths"), nonempty("local_checks"), empty("unresolved")
    elif status == "candidate":
        owner(), nonempty("reviewed_paths"), nonempty("local_checks"), nonempty("result_fingerprints")


def _attempts(unit, base, errors):
    attempts = unit.get("attempts")
    if not isinstance(attempts, list):
        errors.append("%s.attempts: expected array" % base)
        return
    prior_owners, prior_artifacts, previous_wave = set(), set(), 0
    for i, attempt in enumerate(attempts[:LIMITS["collection_items"]]):
        abase = "%s.attempts[%d]" % (base, i)
        if not isinstance(attempt, dict):
            errors.append("%s: expected object" % abase)
            continue
        for field in ATTEMPT_FIELDS:
            if field not in attempt:
                errors.append("%s: missing required field %r" % (abase, field))
        wave = attempt.get("wave")
        if _type_of(wave) != "integer" or wave < 1:
            errors.append("%s.wave: expected a positive integer" % abase)
        else:
            if wave <= previous_wave:
                errors.append("%s.wave: archived attempt waves must be strictly increasing" % abase)
            if _type_of(unit.get("wave")) == "integer" and wave >= unit["wave"]:
                errors.append("%s.wave: archived attempt wave must precede current wave %r" % (abase, unit["wave"]))
            previous_wave = wave
        if not _in(attempt.get("status"), ATTEMPT_STATUSES):
            errors.append('%s.status: expected "covered", "candidate", or "blocked"' % abase)
        fresh = False
        if not safe_agent_id(attempt.get("agent_id")):
            errors.append("%s.agent_id: archived attempt requires a canonical lowercase agent ID" % abase)
        elif _in(attempt["agent_id"], prior_owners):
            errors.append("%s.agent_id: assignment owner must be fresh for each attempt" % abase)
        else:
            fresh = True
        _string_list(attempt.get("reviewed_paths"), abase + ".reviewed_paths", errors, path_value=True)
        _checks(attempt.get("local_checks"), abase + ".local_checks", errors)
        _path_ownership(attempt, abase, errors)
        _string_list(attempt.get("result_fingerprints"), abase + ".result_fingerprints", errors, fingerprint=True)
        _string_list(attempt.get("unresolved"), abase + ".unresolved", errors)
        if not visible_text(attempt.get("reassignment_reason")):
            errors.append("%s.reassignment_reason: invalid text" % abase)
        _state(attempt, abase, errors)
        for j, check in enumerate(_list(attempt.get("local_checks"))):
            if not isinstance(check, dict):
                continue
            if _in(check.get("agent_id"), prior_owners):
                errors.append("%s.local_checks[%d].agent_id: prior assignment owner evidence must remain in its "
                              "earlier attempt" % (abase, j))
            if isinstance(check.get("artifact"), str) and check["artifact"] in prior_artifacts:
                errors.append("%s.local_checks[%d].artifact: artifact from an earlier attempt cannot be reused"
                              % (abase, j))
            if check.get("method") == "local" and isinstance(check.get("artifact"), str):
                prior_artifacts.add(check["artifact"])
        if fresh:
            prior_owners.add(attempt["agent_id"])
    if safe_agent_id(unit.get("agent_id")) and _in(unit["agent_id"], prior_owners):
        errors.append("%s.agent_id: current assignment owner must be fresh after reassignment" % base)
    for j, check in enumerate(_list(unit.get("local_checks"))):
        if not isinstance(check, dict):
            continue
        if _in(check.get("agent_id"), prior_owners):
            errors.append("%s.local_checks[%d].agent_id: prior assignment owner evidence must remain in its archived "
                          "attempt" % (base, j))
        if isinstance(check.get("artifact"), str) and check["artifact"] in prior_artifacts:
            errors.append("%s.local_checks[%d].artifact: artifact from an archived attempt cannot be reused" % (base, j))


def unit_errors(unit, index):
    base = "$[%d]" % index
    if not isinstance(unit, dict):
        return ["%s: expected object" % base]
    errors = []
    for field in LEDGER_FIELDS:
        if field not in unit:
            errors.append("%s: missing required field %r" % (base, field))
    for field in REF_FIELDS:
        if not visible_text(unit.get(field)):
            errors.append("%s.%s: invalid text" % (base, field))
    if "lifecycle" in unit and not visible_text(unit["lifecycle"]):
        errors.append("%s.lifecycle: invalid text" % base)
    expected = None
    refs = unit.get("canonical_refs")
    if not isinstance(refs, dict):
        errors.append("%s.canonical_refs: expected object" % base)
    else:
        fields = REF_FIELDS + (["lifecycle"] if "lifecycle" in refs else [])
        for field in fields:
            if field not in refs:
                errors.append("%s.canonical_refs: missing required field %r" % (base, field))
            elif not canonical_ref(refs[field]):
                errors.append("%s.canonical_refs.%s: invalid canonical reference" % (base, field))
        if any(k not in fields for k in refs):
            errors.append("%s.canonical_refs: contains unexpected fields" % base)
        if ("lifecycle" in unit) != ("lifecycle" in refs):
            errors.append("%s: lifecycle and canonical_refs.lifecycle must appear together" % base)
        try:
            expected = coverage_id(refs)
        except ValueError:
            pass
    if not visible_text(unit.get("coverage_id"), 65536):
        errors.append("%s.coverage_id: invalid text" % base)
    elif expected is not None and unit["coverage_id"] != expected:
        errors.append("%s.coverage_id: expected canonical ID %r" % (base, expected))
    _string_list(unit.get("starting_paths"), base + ".starting_paths", errors, allow_empty=False, path_value=True)
    block = unit.get("ordinary_attack_class_block")
    if block is not None and not visible_text(block):
        errors.append("%s.ordinary_attack_class_block: expected null or non-empty text" % base)
    _string_list(unit.get("selected_companion_blocks"), base + ".selected_companion_blocks", errors)
    excluded = unit.get("excluded_blocks")
    if not isinstance(excluded, list):
        errors.append("%s.excluded_blocks: expected array" % base)
    else:
        sel = unit.get("selected_companion_blocks")
        selected = set(b for b in sel if isinstance(b, str)) if isinstance(sel, list) else set()
        seen = set()
        for i, entry in enumerate(excluded[:LIMITS["collection_items"]]):
            ebase = "%s.excluded_blocks[%d]" % (base, i)
            if not isinstance(entry, dict):
                errors.append("%s: expected object" % ebase)
                continue
            if not visible_text(entry.get("block")):
                errors.append("%s.block: invalid text" % ebase)
            if not visible_text(entry.get("reason")):
                errors.append("%s.reason: invalid text" % ebase)
            if _in(entry.get("block"), seen):
                errors.append("%s.block: duplicate entry" % ebase)
            if _in(entry.get("block"), selected):
                errors.append("%s.block: block is also selected" % ebase)
            if isinstance(entry.get("block"), str):
                seen.add(entry["block"])
    if not _in(unit.get("prior_status"), PRIOR_STATUSES):
        errors.append("%s.prior_status: invalid value %r" % (base, unit.get("prior_status")))
    if not _in(unit.get("status"), STATUSES):
        errors.append("%s.status: invalid value %r" % (base, unit.get("status")))
    if _type_of(unit.get("wave")) != "integer" or unit["wave"] < 1:
        errors.append("%s.wave: expected a positive integer" % base)
    if unit.get("agent_id") is not None and not safe_agent_id(unit.get("agent_id")):
        errors.append("%s.agent_id: expected null or a safe agent ID" % base)
    _attempts(unit, base, errors)
    _string_list(unit.get("reviewed_paths"), base + ".reviewed_paths", errors, path_value=True)
    _checks(unit.get("local_checks"), base + ".local_checks", errors)
    _path_ownership(unit, base, errors)
    _string_list(unit.get("result_fingerprints"), base + ".result_fingerprints", errors, fingerprint=True)
    _string_list(unit.get("unresolved"), base + ".unresolved", errors)
    _state(unit, base, errors)
    return errors


def validate_ledger(ledger):
    if not isinstance(ledger, list):
        return ["$: expected a top-level array"]
    if len(ledger) > LIMITS["units"]:
        return ["$: exceeds %d coverage units" % LIMITS["units"]]
    errors = []
    ids, tuples, previous = {}, {}, None
    for index, unit in enumerate(ledger):
        errors += unit_errors(unit, index)
        if not isinstance(unit, dict):
            continue
        cid = unit.get("coverage_id")
        if isinstance(cid, str):
            if cid in ids:
                same = _canonical({k: v for k, v in unit.items()}) == _canonical(ledger[ids[cid]])
                errors.append("$[%d].coverage_id: %s at $[%d]" % (
                    index, "duplicate ID" if same else "canonical identity collision", ids[cid]))
            else:
                ids[cid] = index
            if previous is not None and previous > cid:
                errors.append("$[%d].coverage_id: units must be sorted lexicographically" % index)
            previous = cid
        key = _canonical([unit.get(f) for f in REF_FIELDS] + [unit.get("lifecycle")])
        if key in tuples and tuples[key][1] != cid:
            errors.append("$[%d].canonical_refs: semantic tuple already uses coverage ID %r at $[%d]"
                          % (index, tuples[key][1], tuples[key][0]))
        tuples.setdefault(key, (index, cid))
        if len(errors) >= LIMITS["errors"]:
            break
    return errors[:LIMITS["errors"]]


def ledger_counts(ledger):
    counts = dict((s, 0) for s in sorted(STATUSES))
    for unit in ledger if isinstance(ledger, list) else []:
        if isinstance(unit, dict) and _in(unit.get("status"), counts):
            counts[unit["status"]] += 1
    return counts


def new_unit(spec):
    """A planned ledger unit from {surface, boundary, subsystem, attack_class, canonical_refs, starting_paths, ...}."""
    refs = dict(spec["canonical_refs"])
    unit = {
        "coverage_id": coverage_id(refs),
        "canonical_refs": refs,
        "surface": spec["surface"],
        "boundary": spec["boundary"],
        "subsystem": spec["subsystem"],
        "attack_class": spec["attack_class"],
        "starting_paths": list(spec["starting_paths"]),
        "ordinary_attack_class_block": spec.get("ordinary_attack_class_block"),
        "selected_companion_blocks": list(spec.get("selected_companion_blocks", [])),
        "excluded_blocks": list(spec.get("excluded_blocks", [])),
        "prior_status": spec.get("prior_status", "none"),
        "attempts": [],
        "wave": 1,
        "status": "planned",
        "agent_id": None,
        "reviewed_paths": [],
        "local_checks": [],
        "result_fingerprints": [],
        "unresolved": [],
    }
    if "lifecycle" in spec:
        unit["lifecycle"] = spec["lifecycle"]
    return unit


def main_validate(kind, path, out=sys.stdout):
    """CLI helper: print errors, return exit code (0 valid, 1 invalid, 2 unreadable)."""
    try:
        data = load_json(path)
    except AuditInputError as exc:
        out.write("INVALID %s\n  %s\n" % (path, exc))
        return 2
    errors = validate_findings(data) if kind == "findings" else validate_ledger(data)
    if errors:
        out.write("INVALID %s (%d error(s))\n" % (path, len(errors)))
        for e in errors:
            out.write("  %s\n" % e)
        return 1
    if kind == "findings":
        verdicts = {}
        for f in data:
            verdicts[f["verdict"]] = verdicts.get(f["verdict"], 0) + 1
        out.write("OK %s: %d record(s) %s\n" % (path, len(data), json.dumps(verdicts, sort_keys=True)))
    else:
        counts = dict((k, v) for k, v in ledger_counts(data).items() if v)
        out.write("OK %s: %d unit(s) %s\n" % (path, len(data), json.dumps(counts, sort_keys=True)))
    return 0
