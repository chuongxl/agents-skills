"""Deep-audit results for the unified report.

Only a findings.json that passes the validator is merged: `confirmed` records become findings
(scanner "audit", type "logic") with their own severity; `needs_validation` records are listed separately
with no severity; `rejected` records are counted only. Coverage comes from coverage-ledger.json. An invalid
or unfinished audit is reported as such and contributes no finding. Stdlib only; Python 3.8+.
"""
import os

import audit

SEVERITY = {"critical": "CRITICAL", "high": "HIGH", "medium": "MEDIUM", "low": "LOW", "informational": "INFO"}


def _location(record):
    trace = record.get("trace") or []
    sink = next((t for t in reversed(trace) if t.get("kind") == "sink"), None) or (trace[-1] if trace else None)
    if sink:
        return sink.get("file"), sink.get("line")
    evidence = record.get("evidence") or []
    return (evidence[0].get("file"), evidence[0].get("line")) if evidence else (None, None)


def _finding(repo, record, workspace):
    file_, line = _location(record)
    sev = record["severity"]
    return {
        "repo": repo, "scanner": "audit", "type": "logic",
        "severity": SEVERITY.get(sev["overall_severity"], "INFO"),
        "file": file_ or "", "line": line, "code": None, "package": "", "installed_version": "", "fixed_version": "",
        "rule_id": record["fingerprint"], "title": record["title"], "description": record["description"][:300],
        "url": "", "verdict": "confirmed", "workspace": workspace,
        "details": {
            "root_cause": record["root_cause"],
            "intended_behavior": record["intended_behavior"],
            "observed_result": record["execution"]["observed_result"],
            "remediation": record["remediation"]["strategy"],
            "likelihood": sev["likelihood"]["score"], "impact": sev["impact"]["score"],
            "confidence": record["confidence"]["score"],
            "trace": ["%s:%s %s" % (t["file"], t["line"], t["scope"]) for t in record["trace"]],
        },
    }


def load(results_dir, repo, workspace):
    """(findings to merge, audit summary) for one repo, or ([], None) when no audit ran."""
    audit_dir = os.path.join(results_dir, repo, "audit")
    if not os.path.isdir(audit_dir):
        return [], None
    summary = {"profile": None, "run_status": None, "execution_policy": None, "source_ref": None,
               "valid": False, "errors": [], "confirmed": 0, "needs_validation": [], "rejected": 0,
               "coverage": None, "deferred": [], "hardening": [], "incomplete_reason": None}
    meta_path = os.path.join(audit_dir, "run-metadata.json")
    try:
        meta = audit.load_json(meta_path)
        if isinstance(meta, dict):
            for k in ("profile", "run_status", "execution_policy", "source_ref", "incomplete_reason"):
                summary[k] = meta.get(k)
    except audit.AuditInputError as exc:
        summary["errors"].append(str(exc))
    ledger_path = os.path.join(audit_dir, "coverage-ledger.json")
    if os.path.isfile(ledger_path):
        try:
            ledger = audit.load_json(ledger_path)
            errors = audit.validate_ledger(ledger)
            if errors:
                summary["errors"] += ["coverage-ledger.json: " + e for e in errors[:5]]
            else:
                summary["coverage"] = dict((k, v) for k, v in audit.ledger_counts(ledger).items() if v)
                for unit in ledger:
                    if unit["status"] in ("deferred", "out_of_scope", "blocked"):
                        summary["deferred"].append({"status": unit["status"], "surface": unit["surface"],
                                                    "attack_class": unit["attack_class"],
                                                    "reason": "; ".join(unit["unresolved"])})
                    for note in unit.get("hardening") or []:
                        if isinstance(note, str) and note.strip() and note not in summary["hardening"]:
                            summary["hardening"].append(note.strip())
        except audit.AuditInputError as exc:
            summary["errors"].append(str(exc))
    findings_path = os.path.join(audit_dir, "findings.json")
    if not os.path.isfile(findings_path):
        if summary["run_status"] in (None, "awaiting_agent", "in_progress"):
            summary["errors"].append("findings.json not written yet - the agent phase has not finished")
        return [], summary
    try:
        records = audit.load_json(findings_path)
    except audit.AuditInputError as exc:
        summary["errors"].append(str(exc))
        return [], summary
    errors = audit.validate_findings(records)
    if errors:
        summary["errors"] += ["findings.json: " + e for e in errors[:10]]
        return [], summary
    if summary["coverage"] is None and not summary["errors"]:
        summary["errors"].append("coverage-ledger.json missing - findings without a coverage claim are not merged")
    if summary["run_status"] not in ("complete", "incomplete"):
        summary["errors"].append("run-metadata.json run_status is %r, not complete or incomplete"
                                 % summary["run_status"])
    if summary["errors"]:
        return [], summary
    summary["valid"] = True
    merged = []
    for record in records:
        if record["verdict"] == "confirmed":
            merged.append(_finding(repo, record, workspace))
        elif record["verdict"] == "needs_validation":
            file_, line = _location(record)
            summary["needs_validation"].append({
                "fingerprint": record["fingerprint"], "title": record["title"], "file": file_, "line": line,
                "claimed_root_cause": record["claimed_root_cause"], "blockers": record["blockers"],
                "local": record["validation_plan"].get("local"),
                "deployment": record["validation_plan"].get("deployment")})
        else:
            summary["rejected"] += 1
    summary["confirmed"] = len(merged)
    return merged, summary
