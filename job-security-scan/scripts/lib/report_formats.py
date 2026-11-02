"""Markdown and JSON security reports built from the normalised findings of generate-report.py.

The reports describe findings and point at remediation guidance; they never offer or perform fixes.
Stdlib only; Python 3.8+.
"""

SEVERITIES = ("CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO")
SCHEMA_VERSION = 1
FINDING_KEYS = ("repo", "scanner", "type", "severity", "file", "line", "code", "package", "installed_version",
                "fixed_version", "rule_id", "title", "description", "url")
STATUS_EMOJI = {"red": "🔴", "yellow": "🟡", "green": "🟢"}


def _counts(findings):
    counts = dict((s, 0) for s in SEVERITIES)
    for f in findings:
        sev = (f.get("severity") or "").upper()
        if sev in counts:
            counts[sev] += 1
    return counts


def _status(counts):
    if counts["CRITICAL"] or counts["HIGH"]:
        return "red"
    if counts["MEDIUM"] or counts["LOW"] or counts["INFO"]:
        return "yellow"
    return "green"


def repo_summaries(findings, repos):
    names = list(repos) + sorted({f["repo"] for f in findings} - set(repos))
    out = []
    for name in names:
        mine = [f for f in findings if f["repo"] == name]
        counts = _counts(mine)
        out.append({"name": name, "status": _status(counts), "counts": counts,
                    "secrets": sum(1 for f in mine if f.get("type") == "secret")})
    return out


def build_json(findings, meta):
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": meta.get("generated_at", ""),
        "team": meta.get("team", ""),
        "org": meta.get("org", ""),
        "config": meta.get("config", ""),
        "run_dir": meta.get("run_dir", ""),
        "scanners": list(meta.get("scanners", [])),
        "counts": _counts(findings),
        "repos": repo_summaries(findings, meta.get("repos", [])),
        "skipped": list(meta.get("skipped", [])),
        "findings": [dict((k, f.get(k)) for k in FINDING_KEYS) for f in findings],
    }


# ── Markdown ─────────────────────────────────────────────────────────────────

def _text(value):
    """Inline text safe inside a Markdown table cell or list item."""
    return str(value or "").replace("\n", " ").replace("|", "\\|").replace("`", "'")


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


def _finding_item(f, with_code=True):
    parts = [p for p in (_location(f), _text(f.get("scanner")), _text(f.get("rule_id"))) if p]
    if f.get("package"):
        pkg = _text(f["package"]) + ("@" + _text(f["installed_version"]) if f.get("installed_version") else "")
        if f.get("fixed_version"):
            pkg += " → fixed in " + _text(f["fixed_version"])
        parts.append(pkg)
    head = "- **%s** (%s) — %s" % (_text(f.get("title")) or "Finding", _text(f.get("repo")), " · ".join(parts))
    lines = [head]
    if with_code and f.get("code"):
        lines.append("    " + _code(f["code"]))
    if f.get("description"):
        lines.append("    " + _text(f["description"])[:300])
    return "\n".join(lines)


SECTIONS = [
    ("## 🔴 Critical Findings", ("CRITICAL",)),
    ("## 🟠 High Findings", ("HIGH",)),
    ("## 🟡 Medium Findings", ("MEDIUM",)),
    ("## 🔵 Low / Info", ("LOW", "INFO")),
]


def build_markdown(findings, meta):
    counts = _counts(findings)
    out = [
        "# Security Scan Report — %s / %s" % (_text(meta.get("team")), _text(meta.get("org"))),
        "",
        "**Date:** %s  " % _text(meta.get("generated_at")),
        "**Config:** %s  " % _code(meta.get("config", "")),
        "**Run folder:** %s  " % _code(meta.get("run_dir", "")),
        "**Repos scanned:** %d  " % len(meta.get("repos", [])),
        "**Scanners:** %s  " % (_text(", ".join(meta.get("scanners", []))) or "—"),
        "**Findings:** %s" % " · ".join("%s %d" % (s, counts[s]) for s in SEVERITIES),
        "",
        "This report lists findings only. It does not change any code.",
        "",
        "---",
        "",
        "## Summary",
        "",
        "| Repo | Critical | High | Medium | Low | Secrets | Status |",
        "|------|:--------:|:----:|:------:|:---:|:-------:|:------:|",
    ]
    for r in repo_summaries(findings, meta.get("repos", [])):
        c = r["counts"]
        out.append("| %s | %d | %d | %d | %d | %d | %s |" % (
            _text(r["name"]), c["CRITICAL"], c["HIGH"], c["MEDIUM"], c["LOW"] + c["INFO"], r["secrets"],
            STATUS_EMOJI[r["status"]]))
    out.append("")
    if not findings:
        out += ["", "**No findings** — every scanned repo is clean.", ""]
    non_secret = [f for f in findings if f.get("type") != "secret"]
    for heading, sevs in SECTIONS:
        rows = [f for f in non_secret if (f.get("severity") or "").upper() in sevs]
        out += ["", heading, ""]
        out += [_finding_item(f) for f in rows] or ["_None._"]
    secrets = [f for f in findings if f.get("type") == "secret"]
    out += ["", "## 🔑 Secrets (values never shown)", ""]
    out += [_finding_item(f, with_code=False) for f in secrets] or ["_None._"]
    out += ["", "## ⏭️ Skipped", ""]
    out += ["- %s" % _text(s) for s in meta.get("skipped", [])] or ["_None._"]
    out += ["", "## 📋 Remediation guidance", "",
            "Guidance for each finding category is in `references/remediation.md` of the job-security-scan skill.",
            ""]
    return "\n".join(out)
