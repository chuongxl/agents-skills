"""Deep-audit results for the unified report.

Only a findings.json that passes the validator is merged: `confirmed` records become findings
(scanner "audit", type "logic") with their own severity; `needs_validation` records are listed separately
with no severity; `rejected` records are counted only. Coverage comes from coverage-ledger.json. An invalid
or unfinished audit is reported as such and contributes no finding. Stdlib only; Python 3.8+.
"""
import hashlib
import html
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


def fingerprint(audit_fingerprint):
    """The audit's own fingerprint mapped onto the report's 16-hex fingerprint space (stable across runs)."""
    return hashlib.sha256(("audit\x1f%s" % audit_fingerprint).encode("utf-8")).hexdigest()[:16]


def _finding(repo, record, workspace):
    """A confirmed audit record as a report finding: it already carries a verdict, so it needs no Phase 9 verification."""
    file_, line = _location(record)
    sev = record["severity"]
    severity = SEVERITY.get(sev["overall_severity"], "INFO")
    return {
        "repo": repo, "scanner": "audit", "type": "logic", "severity": severity,
        "file": file_ or "", "line": line, "code": None, "package": "", "installed_version": "", "fixed_version": "",
        "rule_id": "deep-audit",
        "title": record["title"], "description": record["description"][:300], "url": "",
        "workspace": workspace, "fingerprint": fingerprint(record["fingerprint"]),
        "verdict": "confirmed", "verified_severity": severity,
        "verdict_detail": {
            "evidence": record["execution"]["observed_result"],
            "likelihood": sev["likelihood"]["score"], "impact": sev["impact"]["score"],
            "root_cause": record["root_cause"], "intended_behavior": record["intended_behavior"],
            "remediation_guidance": record["remediation"]["strategy"],
            "confidence": record["confidence"]["score"],
            "trace": ["%s:%s %s" % (t["file"], t["line"], t["scope"]) for t in record["trace"]],
            "audit_fingerprint": record["fingerprint"],
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


# ── report section ───────────────────────────────────────────────────────────

def build(summaries):
    """The report's `audit` object: {repo: summary} for repos that have an audit folder (or None)."""
    return dict((r, s) for r, s in summaries.items() if s) or None


def validate(doc, err):
    """Report-validator rules for the optional top-level `audit` object."""
    section = doc.get("audit")
    if section is None:
        section = {}
    if not isinstance(section, dict):
        err("audit must be an object keyed by repo")
        return
    counts = {}
    held = list(doc.get("findings", [])) + list((doc.get("baseline") or {}).get("accepted", []))
    for f in held:
        if isinstance(f, dict) and f.get("scanner") == "audit":
            counts[f.get("repo")] = counts.get(f.get("repo"), 0) + 1
    for repo, s in section.items():
        where = "audit[%s]" % repo
        if not isinstance(s, dict) or not isinstance(s.get("valid"), bool):
            err("%s: must be an object with a boolean 'valid'" % where)
            continue
        if not isinstance(s.get("needs_validation"), list) or not isinstance(s.get("errors"), list):
            err("%s: needs_validation and errors must be lists" % where)
            continue
        if s["valid"] and s.get("confirmed") != counts.get(repo, 0):
            err("%s: confirmed (%r) does not match the audit findings in the report (%d)"
                % (where, s.get("confirmed"), counts.get(repo, 0)))
        if not s["valid"] and counts.get(repo):
            err("%s: an invalid audit must not contribute findings" % where)
    for repo in counts:
        if repo not in section:
            err("audit findings for %r but no audit section" % repo)


def render_markdown(doc, text, code):
    section = doc.get("audit")
    if not section:
        return []
    out = ["", "## 🧠 Deep audit", "",
           "Agent-driven code review (reconnaissance, coverage-tracked hunting, adversarial validation, "
           "independent verification). Confirmed findings are listed with the others above, scanner `audit`.", ""]
    for repo in sorted(section):
        s = section[repo]
        ref = s.get("source_ref") or {}
        commit = (ref.get("commit") or "")[:12]
        out.append("### %s — %s" % (text(repo), "complete" if s.get("run_status") == "complete" and s["valid"]
                                    else "incomplete or not merged"))
        out.append("")
        out.append("- Profile %s · policy %s · source %s%s" % (
            text(s.get("profile")), text(s.get("execution_policy")), code(commit) if commit else "unknown",
            " (uncommitted changes)" if ref.get("dirty") else ""))
        if s.get("coverage"):
            out.append("- Coverage: " + ", ".join("%s %d" % (text(k), v) for k, v in sorted(s["coverage"].items())))
        out.append("- Confirmed %d · need validation %d · rejected %d" % (
            s.get("confirmed", 0), len(s["needs_validation"]), s.get("rejected", 0)))
        if s.get("incomplete_reason"):
            out.append("- Incomplete: %s" % text(s["incomplete_reason"]))
        for e in s["errors"]:
            out.append("- ⚠️ %s" % text(e))
        for lead in s["needs_validation"]:
            where = code("%s:%s" % (lead["file"], lead["line"]) if lead.get("line") else lead["file"]) \
                if lead.get("file") else "—"
            out.append("- ❓ **%s** — %s — blocker: %s" % (text(lead.get("title")), where,
                                                          text("; ".join(lead.get("blockers") or []))[:400]))
        for d in s["deferred"]:
            out.append("- ⏭️ %s: %s / %s — %s" % (text(d["status"]), text(d["surface"]), text(d["attack_class"]),
                                                  text(d["reason"])[:300]))
        for note in s["hardening"][:10]:
            out.append("- 🛡️ hardening note: %s" % text(note)[:300])
        out.append("")
    return out


def render_html(doc):
    section = doc.get("audit")
    if not section:
        return ""
    e = html.escape
    parts = ['<div class="runinfo" id="deep-audit"><div><strong>🧠 Deep audit</strong> — confirmed findings appear '
             'in the table below (scanner <code>audit</code>); leads that could not be confirmed are listed here.'
             '</div>']
    for repo in sorted(section):
        s = section[repo]
        ref = s.get("source_ref") or {}
        parts.append("<div><strong>%s</strong>: profile %s · source <code>%s</code>%s · confirmed %d · need "
                     "validation %d · rejected %d</div>" % (
                         e(repo), e(str(s.get("profile"))), e((ref.get("commit") or "unknown")[:12]),
                         " (uncommitted changes)" if ref.get("dirty") else "", s.get("confirmed", 0),
                         len(s["needs_validation"]), s.get("rejected", 0)))
        if s.get("coverage"):
            parts.append("<div>Coverage: %s</div>" % e(", ".join("%s %d" % (k, v)
                                                                  for k, v in sorted(s["coverage"].items()))))
        for msg in s["errors"]:
            parts.append("<div>⚠️ %s</div>" % e(str(msg)))
        if s["needs_validation"]:
            parts.append("<ul>" + "".join(
                "<li>❓ %s — <code>%s</code> — blocker: %s</li>" % (
                    e(str(l.get("title") or "")), e("%s:%s" % (l.get("file") or "", l.get("line") or "")),
                    e("; ".join(l.get("blockers") or [])[:400])) for l in s["needs_validation"]) + "</ul>")
        if s["deferred"]:
            parts.append("<ul>" + "".join(
                "<li>⏭️ %s: %s / %s — %s</li>" % (e(d["status"]), e(d["surface"]), e(d["attack_class"]),
                                                  e(d["reason"][:300])) for d in s["deferred"]) + "</ul>")
    parts.append("</div>")
    return "\n".join(parts)
