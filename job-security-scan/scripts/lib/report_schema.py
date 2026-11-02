"""Validator for security-report.json v2 — the enforced contract (assets/report.schema.json mirrors it).

Structural checks plus the semantic rules a JSON Schema cannot express: unique fingerprints, counts that match
the findings, the verdict contract, severity never above demonstrated impact, and no code on secret rows.
Stdlib only; Python 3.8+.
"""

from report_model import (CHANGES, IMPACTS, LIKELIHOODS, PROFILES, SCHEMA_VERSION, SEVERITIES, VERDICTS,
                          counts_of, verification_summary)

MAX_FINDINGS = 20000
MAX_ERRORS = 100
TOP_KEYS = ("schema_version", "generated_at", "team", "org", "run_dir", "run", "scanners", "counts", "repos",
            "fixed", "verification", "findings")
FINDING_REQUIRED = ("repo", "scanner", "type", "severity", "file", "line", "code", "rule_id", "title",
                    "fingerprint", "change", "verdict", "verified_severity", "verdict_detail")
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
    if doc.get("schema_version") != SCHEMA_VERSION:
        return ["schema_version must be %d (got %r) - regenerate the report with this version"
                % (SCHEMA_VERSION, doc.get("schema_version"))]
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
    if not errors:
        if doc["counts"] != counts_of(findings):
            err("counts do not match the findings (rejected findings are excluded, confirmed use verified severity)")
        if doc["verification"] != verification_summary(findings, run.get("profile")):
            err("verification summary does not match the findings")
    return errors
