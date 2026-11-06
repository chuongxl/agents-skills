"""Validator for the security report (a v2 file, a v3 index, or a whole v3 report in memory) — the enforced
contract (assets/report.schema.json mirrors it).

Structural checks plus the semantic rules a JSON Schema cannot express: unique fingerprints, counts that match
the findings, the verdict contract, severity never above demonstrated impact, and no code on secret rows.
Stdlib only; Python 3.8+.
"""

import re

import audit_report
import baseline
import report_shaihulud
from report_model import (CHANGES, IMPACTS, LIKELIHOODS, PROFILES, SCHEMA_VERSION, SEVERITIES, VERDICTS,
                          counts_of, verification_summary)

MAX_FINDINGS = 200000
MAX_ERRORS = 100
TOP_KEYS = ("schema_version", "generated_at", "team", "org", "run_dir", "run", "scanners", "counts", "repos",
            "fixed", "shai_hulud", "verification", "findings")
FINDING_REQUIRED = ("repo", "scanner", "type", "severity", "file", "line", "code", "rule_id", "title",
                    "fingerprint", "change", "verdict", "verified_severity", "verdict_detail")
READABLE_VERSIONS = (2, SCHEMA_VERSION)
SHARD_KEYS = ("file", "repo", "count", "bytes", "sha256")
_SHARD_FILE = re.compile(r"^findings/[A-Za-z0-9._-]+\.json$")
_IMPACT_RANK = dict((v, i) for i, v in enumerate(IMPACTS))
_SEV_RANK = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "INFO": 4}


def validate_verdict(verdict, verified_severity, detail, where="verdict"):
    """Errors for one verdict record (shared by the report validator and triage.py apply)."""
    errors = []
    if verdict is None:
        if verified_severity:
            errors.append("%s: verified_severity without a verdict" % where)
        return errors
    if verdict not in VERDICTS:
        return ["%s: verdict must be one of %s" % (where, ", ".join(VERDICTS))]
    if not isinstance(detail, dict):
        return ["%s: verdict_detail must be an object" % where]

    def need(key):
        if not str(detail.get(key) or "").strip():
            errors.append("%s: %s verdict requires '%s'" % (where, verdict, key))

    if verdict == "confirmed":
        need("evidence")
        if detail.get("likelihood") not in LIKELIHOODS:
            errors.append("%s: confirmed verdict requires likelihood in %s" % (where, ", ".join(LIKELIHOODS)))
        if detail.get("impact") not in IMPACTS:
            errors.append("%s: confirmed verdict requires impact in %s" % (where, ", ".join(IMPACTS)))
        if verified_severity not in SEVERITIES:
            errors.append("%s: confirmed verdict requires verified_severity in %s" % (where, ", ".join(SEVERITIES)))
        elif detail.get("impact") in _IMPACT_RANK and _SEV_RANK[verified_severity] < _IMPACT_RANK[detail["impact"]]:
            errors.append("%s: verified_severity %s exceeds demonstrated impact %s"
                          % (where, verified_severity, detail["impact"]))
        for banned in ("blocker", "reason"):
            if detail.get(banned):
                errors.append("%s: confirmed verdict must not carry '%s'" % (where, banned))
    elif verdict == "needs_validation":
        need("blocker")
        need("validation_plan")
        if verified_severity:
            errors.append("%s: needs_validation must not carry verified_severity" % where)
    else:  # rejected
        need("reason")
        if verified_severity:
            errors.append("%s: rejected must not carry verified_severity" % where)
    return errors


def validate(doc):
    errors = []

    def err(msg):
        if len(errors) < MAX_ERRORS:
            errors.append(msg)

    if not isinstance(doc, dict):
        return ["report must be a JSON object"]
    if doc.get("schema_version") not in READABLE_VERSIONS:
        return ["schema_version must be one of %s (got %r) - regenerate the report with this version"
                % (", ".join(map(str, READABLE_VERSIONS)), doc.get("schema_version"))]
    for k in TOP_KEYS:
        if k not in doc:
            err("missing top-level key '%s'" % k)
    if errors:
        return errors
    run = doc["run"]
    if not isinstance(run, dict) or run.get("profile") not in PROFILES:
        err("run.profile must be one of %s" % ", ".join(PROFILES))
    findings = doc["findings"]
    if not isinstance(findings, list):
        return errors + ["findings must be a list"]
    if len(findings) > MAX_FINDINGS:
        return errors + ["more than %d findings" % MAX_FINDINGS]
    seen = set()
    for i, f in enumerate(findings):
        where = "findings[%d]" % i
        if not isinstance(f, dict):
            err("%s: must be an object" % where)
            continue
        for k in FINDING_REQUIRED:
            if k not in f:
                err("%s: missing '%s'" % (where, k))
        fp = f.get("fingerprint")
        if not isinstance(fp, str) or len(fp) != 16:
            err("%s: fingerprint must be 16 hex characters" % where)
        elif fp in seen:
            err("%s: duplicate fingerprint %s" % (where, fp))
        seen.add(fp)
        if f.get("severity") not in SEVERITIES:
            err("%s: severity must be one of %s" % (where, ", ".join(SEVERITIES)))
        if f.get("change") not in CHANGES:
            err("%s: change must be one of %s" % (where, ", ".join(CHANGES)))
        if f.get("line") is not None and (not isinstance(f["line"], int) or f["line"] < 1):
            err("%s: line must be a positive integer or null" % where)
        if f.get("type") == "secret" and f.get("code"):
            err("%s: a secret finding must not carry a code excerpt" % where)
        for e in validate_verdict(f.get("verdict"), f.get("verified_severity"), f.get("verdict_detail"), where):
            err(e)
    report_shaihulud.validate(doc, err)
    audit_report.validate(doc, err)
    baseline.validate(doc, err)
    if not errors:
        if doc["counts"] != counts_of(findings):
            err("counts do not match the findings (rejected findings are excluded, confirmed use verified severity)")
        if doc["verification"] != verification_summary(findings, run.get("profile")):
            err("verification summary does not match the findings")
    return errors


def validate_index(index):
    """Errors for a v3 index (security-report.json without findings; see report_store)."""
    if not isinstance(index, dict):
        return ["report index must be a JSON object"]
    if index.get("schema_version") != SCHEMA_VERSION:
        return ["index schema_version must be %d (got %r)" % (SCHEMA_VERSION, index.get("schema_version"))]
    errors = ["missing top-level key '%s'" % k for k in TOP_KEYS + ("findings_total", "shards", "fixed_shards")
              if k != "findings" and k not in index]
    if "findings" in index:
        errors.append("a v3 index must not hold findings inline")
    if errors:
        return errors
    total = 0
    for name in ("shards", "fixed_shards"):
        shards = index[name]
        if not isinstance(shards, list):
            errors.append("%s must be a list" % name)
            continue
        for i, s in enumerate(shards):
            where = "%s[%d]" % (name, i)
            if not isinstance(s, dict) or any(k not in s for k in SHARD_KEYS):
                errors.append("%s: needs %s" % (where, ", ".join(SHARD_KEYS)))
                continue
            if not isinstance(s["file"], str) or not _SHARD_FILE.match(s["file"]):
                errors.append("%s: file must be findings/<name>.json" % where)
            if not isinstance(s["count"], int) or s["count"] < 0:
                errors.append("%s: count must be a non-negative integer" % where)
            elif name == "shards":
                total += s["count"]
    if not errors and total != index["findings_total"]:
        errors.append("shard counts add up to %d, findings_total is %r" % (total, index["findings_total"]))
    return errors[:MAX_ERRORS]
