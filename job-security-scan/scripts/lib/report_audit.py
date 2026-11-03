"""The Code audit section of the reports (SKILL.md Phase 10): which units (repo x area x attack class) were
audited and how each ended, which were deferred over the budget, hunter replies that were refused, hardening
notes, and the candidates still waiting for an independent verifier (they are not counted until verified).

Built from RUN/triage/audit-plan.json and RUN/triage/audit-ledger.json (written by scripts/audit.py).
Stdlib only; Python 3.8+.
"""

import html
import json
from pathlib import Path

from shaihulud.findings import redact

STATUSES = ("covered", "candidate", "blocked", "deferred", "failed", "not-run")
LABEL = {"covered": "✅ covered", "candidate": "🔎 candidate", "blocked": "⛔ blocked", "deferred": "⏳ deferred",
         "failed": "⚠️ reply refused", "not-run": "⏭️ not run"}
MAX_BYTES = 5 * 1024 * 1024


def _load(path):
    try:
        if path.stat().st_size > MAX_BYTES:
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _strs(value, n, limit=300):
    return [redact(str(x))[:limit] for x in value[:n]] if isinstance(value, list) else []


def build(run_dir):
    """The `code_audit` block of security-report.json."""
    run_dir = Path(run_dir)
    plan = _load(run_dir / "triage" / "audit-plan.json")
    if plan is None:
        return {"ran": False, "profile": None, "budget": 0, "classes": [], "units": [], "rejected_results": []}
    ledger = _load(run_dir / "triage" / "audit-ledger.json") or {}
    done = dict((u.get("id"), u) for u in ledger.get("units", []) if isinstance(u, dict))
    units = []
    for u in plan.get("units", []):
        if not isinstance(u, dict):
            continue
        l = done.get(u.get("id"), {})
        status = l.get("status") if l.get("status") in STATUSES else ("deferred" if u.get("status") == "deferred"
                                                                      else "not-run")
        units.append({
            "id": str(u.get("id"))[:200], "repo": str(u.get("repo"))[:100], "area": str(u.get("area"))[:100],
            "attack_class": str(u.get("attack_class"))[:40], "wave": u.get("wave") if isinstance(u.get("wave"), int) else 1,
            "status": status, "reason": redact(str(u.get("reason") or l.get("reason") or ""))[:200],
            "reviewed": len(l.get("reviewed_paths") or []) if isinstance(l.get("reviewed_paths"), list) else 0,
            "candidates": l.get("candidates") if isinstance(l.get("candidates"), int) else 0,
            "hardening": _strs(l.get("hardening"), 10), "unresolved": _strs(l.get("unresolved"), 5),
        })
    rejected = [{"file": redact(str(r.get("file")))[:120], "unit": redact(str(r.get("unit")))[:200] if r.get("unit") else None,
                 "reason": redact(str(r.get("reason")))[:300]}
                for r in ledger.get("rejected_results", [])[:50] if isinstance(r, dict)]
    return {"ran": True, "profile": plan.get("profile"), "budget": plan.get("budget") if isinstance(plan.get("budget"), int) else 0,
            "classes": [str(c) for c in plan.get("classes", [])][:20], "units": units, "rejected_results": rejected}


def validate(doc, err):
    ca = doc.get("code_audit")
    if not isinstance(ca, dict) or not isinstance(ca.get("units"), list) or not isinstance(ca.get("ran"), bool):
        err("code_audit: must be an object with 'ran' (true/false) and 'units' (list)")
        return
    findings = [f for f in doc.get("findings", []) if isinstance(f, dict) and f.get("scanner") == "code-audit"]
    if findings and not ca["ran"]:
        err("code_audit: code-audit findings but the audit did not run")
    has_candidate = False
    for i, u in enumerate(ca["units"]):
        where = "code_audit.units[%d]" % i
        if not isinstance(u, dict) or u.get("status") not in STATUSES:
            err("%s: status must be one of %s" % (where, ", ".join(STATUSES)))
            continue
        n = u.get("candidates", 0)
        if u["status"] == "candidate":
            has_candidate = True
            if not isinstance(n, int) or n < 1:
                err("%s: a candidate unit needs at least one candidate" % where)
        elif n:
            err("%s: status %s but %s candidate(s)" % (where, u["status"], n))
    if findings and not has_candidate:
        err("code_audit: %d code-audit finding(s) but no unit with status candidate" % len(findings))


# ── rendering ────────────────────────────────────────────────────────────────

def _pending(doc):
    return [f for f in doc.get("findings", []) if f.get("scanner") == "code-audit" and not f.get("verdict")]


def _summary(ca):
    counts = {}
    for u in ca["units"]:
        counts[u["status"]] = counts.get(u["status"], 0) + 1
    return " · ".join("%d %s" % (counts[s], s) for s in STATUSES if counts.get(s))


def render_markdown(doc, text, code):
    ca = doc.get("code_audit") or {"ran": False, "units": []}
    out = ["", "## 🔎 Code audit", ""]
    if not ca.get("ran"):
        return out + ["_The code audit did not run in this scan (agents audit the code by attack class with "
                      "`--profile deep` or on request; SKILL.md Phase 10)._"]
    out += ["Profile %s · budget %d units · classes: %s" % (text(ca.get("profile")), ca.get("budget", 0),
                                                              text(", ".join(ca.get("classes", [])))),
            "", "Units: %s. Candidates count only once an independent verifier confirms them." % (_summary(ca) or "none")]
    pending = _pending(doc)
    out += ["", "**Pending verification** (not counted yet):", ""]
    if pending:
        for f in pending:
            where = code("%s:%s" % (f["file"], f["line"])) if f.get("line") else code(f.get("file") or "")
            out.append("- **%s** (%s) — %s · %s · proposed %s · %s" % (
                text(f.get("title")), text(f.get("repo")), where, text(f.get("rule_id")), text(f.get("severity")),
                text(f.get("description"))[:200]))
    else:
        out.append("_None._")
    out += ["", "| Unit | Result | Files read | Notes |", "|---|---|---|---|"]
    for u in ca["units"]:
        notes = u.get("reason") or "; ".join(u.get("unresolved") or [])
        if u["status"] == "candidate":
            notes = "%d candidate(s)" % u.get("candidates", 0)
        out.append("| %s | %s | %s | %s |" % (code(u["id"]), text(LABEL[u["status"]]), u.get("reviewed", 0) or "—",
                                             text(notes) or "—"))
    if ca.get("rejected_results"):
        out += ["", "Hunter replies refused (not repaired; re-run the unit and collect again):", ""]
        out += ["- %s (%s): %s" % (code(r["file"]), text(r.get("unit") or "?"), text(r["reason"]))
                for r in ca["rejected_results"]]
    notes = []
    for u in ca["units"]:
        for h in u.get("hardening") or []:
            if h not in notes:
                notes.append(h)
    if notes:
        out += ["", "Hardening notes (not findings):", ""] + ["- %s" % text(h) for h in notes[:20]]
    return out


def render_html(doc):
    ca = doc.get("code_audit") or {"ran": False, "units": []}
    e = html.escape
    if not ca.get("ran"):
        return '<div class="runinfo" id="code-audit"><strong>🔎 Code audit:</strong> did not run in this scan.</div>'
    pending = "".join("<li>%s (%s) — <code>%s:%s</code> · %s · proposed %s</li>" % (
        e(str(f.get("title"))), e(str(f.get("repo"))), e(str(f.get("file"))), e(str(f.get("line") or "")),
        e(str(f.get("rule_id"))), e(str(f.get("severity")))) for f in _pending(doc)) or "<li>none</li>"
    rows = "".join("<tr><td><code>%s</code></td><td>%s</td><td>%s</td><td>%s</td></tr>" % (
        e(u["id"]), e(LABEL[u["status"]]), u.get("reviewed", 0) or "—",
        e(("%d candidate(s)" % u.get("candidates", 0)) if u["status"] == "candidate"
          else (u.get("reason") or "; ".join(u.get("unresolved") or []) or "—"))) for u in ca["units"])
    return ('<div class="runinfo" id="code-audit"><div><strong>🔎 Code audit</strong> — profile %s, budget %d units: '
            '%s</div><div>Pending verification (not counted yet):<ul>%s</ul></div>'
            '<table class="sh-table"><thead><tr><th>Unit</th><th>Result</th><th>Files read</th><th>Notes</th></tr>'
            '</thead><tbody>%s</tbody></table></div>' % (e(str(ca.get("profile"))), ca.get("budget", 0),
                                                          e(_summary(ca)), pending, rows))
