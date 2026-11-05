"""Markdown and JSON security reports built from the normalised findings of generate-report.py.

The JSON is the v2 document from report_model; the Markdown is rendered from that document, so a report
regenerated after verification (triage.py apply) matches the JSON exactly.
The reports describe findings and point at remediation guidance; they never offer or perform fixes.
Stdlib only; Python 3.8+.
"""

import audit_report
import baseline
import report_model
import report_shaihulud
from report_model import SEVERITIES, SCHEMA_VERSION, FINDING_KEYS, effective_severity  # noqa: F401 (re-export)

STATUS_EMOJI = {"red": "🔴", "yellow": "🟡", "green": "🟢"}
VERDICT_LABEL = {"confirmed": "✅ confirmed", "needs_validation": "❓ needs validation", "rejected": "🚫 dismissed"}


def repo_summaries(findings, repos):
    return report_model.repo_summaries(findings, repos)


def build_json(findings, meta, previous=None):
    return report_model.build_document(findings, meta, previous=previous)


# ── Markdown ─────────────────────────────────────────────────────────────────

def _text(value):
    """Inline text safe inside a Markdown table cell or list item. Scanner output can carry text from the
    scanned repo, so raw HTML is neutralised (Markdown viewers render it)."""
    return (str(value or "").replace("\n", " ").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace("|", "\\|").replace("`", "'"))


def _code(value):
    """A code span that survives backticks in the code itself."""
    value = str(value).replace("\n", " ")
    if "`" not in value:
        return "`%s`" % value
    return "`` %s ``" % value


def _location(f):
    if not f.get("file"):
        return ""
    return _code("%s:%s" % (f["file"], f["line"]) if f.get("line") else f["file"])


def _verdict_line(f):
    v = f.get("verdict")
    if not v:
        return ""
    d = f.get("verdict_detail") or {}
    carried = " (carried from the previous run)" if f.get("carried") else ""
    if v == "confirmed":
        sev = f.get("verified_severity")
        tool = (f.get("severity") or "").upper()
        note = " — tool said %s" % tool if sev and sev != tool else ""
        return "    %s as %s%s%s: %s" % (VERDICT_LABEL[v], sev, note, carried, _text(d.get("evidence"))[:400])
    if v == "needs_validation":
        return "    %s%s — blocker: %s" % (VERDICT_LABEL[v], carried, _text(d.get("blocker"))[:400])
    return "    %s%s — %s" % (VERDICT_LABEL[v], carried, _text(d.get("reason"))[:400])


def _finding_item(f, with_code=True):
    parts = [p for p in (_location(f), _text(f.get("scanner")), _text(f.get("rule_id"))) if p]
    if f.get("package"):
        pkg = _text(f["package"]) + ("@" + _text(f["installed_version"]) if f.get("installed_version") else "")
        if f.get("fixed_version"):
            pkg += " → fixed in " + _text(f["fixed_version"])
        parts.append(pkg)
    new = "🆕 " if f.get("change") == "new" else ""
    head = "- %s**%s** (%s) — %s" % (new, _text(f.get("title")) or "Finding", _text(f.get("repo")), " · ".join(parts))
    lines = [head]
    if with_code and f.get("code") and f.get("type") != "secret":
        lines.append("    " + _code(f["code"]))
    if f.get("description"):
        lines.append("    " + _text(f["description"])[:300])
    verdict = _verdict_line(f)
    if verdict:
        lines.append(verdict)
    return "\n".join(lines)


SECTIONS = [
    ("## 🔴 Critical Findings", ("CRITICAL",)),
    ("## 🟠 High Findings", ("HIGH",)),
    ("## 🟡 Medium Findings", ("MEDIUM",)),
    ("## 🔵 Low / Info", ("LOW", "INFO")),
]


def _changes_section(doc):
    run = doc.get("run") or {}
    rows = doc["findings"]
    out = ["", "## 🔁 Changes since last run", ""]
    if run.get("previous_error"):
        return out + ["_Change tracking unavailable: %s. Nothing is marked fixed in this run._"
                      % _text(run["previous_error"])]
    if not run.get("previous_run"):
        return out + ["_No earlier run to compare with (no older `security-run-*` folder with a readable report)._"]
    new = sum(1 for f in rows if f.get("change") == "new")
    out.append("Compared with %s: **%d new** · %d unchanged · %d fixed" % (
        _code(run["previous_run"]), new, len(rows) - new, len(doc.get("fixed", []))))
    if run.get("partial"):
        out += ["", "_Partial run (%s): fixed findings are not worked out for a partial run._"
                % _text("--since " + run["since"] if run.get("since") else "limited scope")]
    elif doc.get("fixed"):
        out += ["", "Fixed since the previous run (no longer reported by a scanner that ran both times):", ""]
        for f in doc["fixed"]:
            where = _code(f["file"]) if f.get("file") else ""
            out.append("- ✔️ **%s** (%s) — %s" % (_text(f.get("title")) or "Finding", _text(f.get("repo")),
                                                  " · ".join(p for p in (where, _text(f.get("scanner")),
                                                                         _text(f.get("rule_id"))) if p)))
    return out


def render_markdown(doc):
    counts = doc["counts"]
    run = doc.get("run") or {}
    ver = doc.get("verification") or {}
    scope = "partial — only files changed since %s" % _code(run["since"]) if run.get("since") else "full"
    out = [
        "# Security Scan Report — %s / %s" % (_text(doc.get("team")), _text(doc.get("org"))),
        "",
        "**Date:** %s  " % _text(doc.get("generated_at")),
        "**Config:** %s  " % _code(doc.get("config", "")),
        "**Run folder:** %s  " % _code(doc.get("run_dir", "")),
        "**Profile:** %s · **Scope:** %s  " % (_text(run.get("profile")), scope),
        "**Repos scanned:** %d  " % len(doc.get("repos", [])),
        "**Scanners:** %s  " % (_text(", ".join(doc.get("scanners", []))) or "—"),
        "**Findings:** %s  " % " · ".join("%s %d" % (s, counts[s]) for s in SEVERITIES),
        "**Verification:** %d queued · %d pending · %d confirmed · %d need validation · %d dismissed" % (
            ver.get("queued", 0), ver.get("pending", 0), ver.get("confirmed", 0), ver.get("needs_validation", 0),
            ver.get("rejected", 0)),
        "",
        "This report lists findings only. It does not change any code.",
    ]
    if ver.get("pending"):
        out += ["", "> %d finding(s) are waiting for independent verification (SKILL.md Phase 10). Until then "
                "their severity is the scanner's own." % ver["pending"]]
    out += [
        "",
        "---",
        "",
        "## Summary",
        "",
        "| Repo | Critical | High | Medium | Low | Secrets | Status |",
        "|------|:--------:|:----:|:------:|:---:|:-------:|:------:|",
    ]
    for r in doc["repos"]:
        c = r["counts"]
        out.append("| %s | %d | %d | %d | %d | %d | %s |" % (
            _text(r["name"]), c["CRITICAL"], c["HIGH"], c["MEDIUM"], c["LOW"] + c["INFO"], r["secrets"],
            STATUS_EMOJI[r["status"]]))
    out.append("")
    out += report_shaihulud.render_markdown(doc, _text, _code)
    out += audit_report.render_markdown(doc, _text, _code)
    out += baseline.render_markdown(doc, _text, _code)
    out += _changes_section(doc)
    active = [f for f in doc["findings"] if f.get("verdict") != "rejected"]
    if not active:
        out += ["", "**No findings** — every scanned repo is clean.", ""]
    non_secret = [f for f in active if f.get("type") != "secret"]
    for heading, sevs in SECTIONS:
        rows = [f for f in non_secret if effective_severity(f) in sevs]
        out += ["", heading, ""]
        out += [_finding_item(f) for f in rows] or ["_None._"]
    secrets = [f for f in active if f.get("type") == "secret"]
    out += ["", "## 🔑 Secrets (values never shown)", ""]
    out += [_finding_item(f, with_code=False) for f in secrets] or ["_None._"]
    dismissed = [f for f in doc["findings"] if f.get("verdict") == "rejected"]
    if dismissed:
        out += ["", "## 🚫 Dismissed (with reason)", "",
                "Rejected by independent verification; not counted above. Each line says why.", ""]
        out += [_finding_item(f, with_code=False) for f in dismissed]
    out += ["", "## ⏭️ Skipped", ""]
    out += ["- %s" % _text(s) for s in doc.get("skipped", [])] or ["_None._"]
    out += ["", "## 📋 Remediation guidance", "",
            "Guidance for each finding category is in `references/remediation.md` of the job-security-scan skill.",
            ""]
    return "\n".join(out)


def build_markdown(findings, meta, previous=None):
    return render_markdown(report_model.build_document(findings, meta, previous=previous))


def render_needs_validation(doc):
    """NEEDS-VALIDATION.md: findings an independent verifier could neither confirm nor reject."""
    rows = [f for f in doc["findings"] if f.get("verdict") == "needs_validation"]
    out = ["# Findings that need validation — %s / %s" % (_text(doc.get("team")), _text(doc.get("org"))), "",
           "Run folder: %s" % _code(doc.get("run_dir", "")), "",
           "Each finding below could not be confirmed or ruled out from the repository alone. The blocker is the "
           "exact fact that is missing; the plan says how a person can settle it. This file lists work for people; "
           "the skill does not change any code.", ""]
    if not rows:
        return "\n".join(out + ["_None._", ""])
    for f in rows:
        d = f.get("verdict_detail") or {}
        out += ["## %s — %s" % (_text(f.get("title")) or "Finding", _text(f.get("repo"))), "",
                "- **Where:** %s" % (_location(f) or "—"),
                "- **Scanner / rule:** %s / %s" % (_text(f.get("scanner")), _text(f.get("rule_id"))),
                "- **Tool severity:** %s" % _text(f.get("severity")),
                "- **Fingerprint:** %s" % _code(f.get("fingerprint")),
                "- **Blocker:** %s" % _text(d.get("blocker")),
                "- **How to validate:** %s" % _text(d.get("validation_plan")), ""]
    return "\n".join(out)
