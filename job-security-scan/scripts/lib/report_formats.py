"""Markdown and JSON security reports built from the normalised findings of generate-report.py.

The reports describe findings and point at remediation guidance; they never offer or perform fixes.
Stdlib only; Python 3.8+.
"""

SEVERITIES = ("CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO")
SCHEMA_VERSION = 2   # v2 adds fingerprint/diff/verdict/details per finding and diff/baseline/audit sections
FINDING_KEYS = ("repo", "scanner", "type", "severity", "file", "line", "code", "package", "installed_version",
                "fixed_version", "rule_id", "title", "description", "url",
                "fingerprint", "diff_status", "first_seen", "verdict", "details")
ACCEPTED_KEYS = FINDING_KEYS + ("baseline_reason", "baseline_expires", "baseline_owner")
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


def repo_summaries(findings, repos, source_refs=None):
    names = list(repos) + sorted({f["repo"] for f in findings} - set(repos))
    out = []
    for name in names:
        mine = [f for f in findings if f["repo"] == name]
        counts = _counts(mine)
        out.append({"name": name, "status": _status(counts), "counts": counts,
                    "secrets": sum(1 for f in mine if f.get("type") == "secret"),
                    "new": sum(1 for f in mine if f.get("diff_status") == "new"),
                    "source_ref": (source_refs or {}).get(name)})
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
        "repos": repo_summaries(findings, meta.get("repos", []), meta.get("source_refs")),
        "skipped": list(meta.get("skipped", [])),
        "run_options": meta.get("run_options", {}),
        "findings": [dict((k, f.get(k)) for k in FINDING_KEYS) for f in findings],
        "diff": _diff_json(meta.get("diff")),
        "baseline": _baseline_json(meta.get("baseline")),
        "audit": meta.get("audits") or {},
    }


def _diff_json(diff):
    if not diff:
        return None
    out = dict((k, v) for k, v in diff.items() if k != "fixed_findings")
    out["fixed_findings"] = list(diff.get("fixed_findings", []))
    return out


def _baseline_json(baseline):
    baseline = baseline or {}
    return {"path": baseline.get("path"),
            "accepted": [dict((k, f.get(k)) for k in ACCEPTED_KEYS) for f in baseline.get("accepted", [])],
            "unused": list(baseline.get("unused", [])), "expired": list(baseline.get("expired", [])),
            "invalid": list(baseline.get("invalid", []))}


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


def _finding_item(f, with_code=True):
    parts = [p for p in (_location(f), _text(f.get("scanner")), _text(f.get("rule_id"))) if p]
    if f.get("package"):
        pkg = _text(f["package"]) + ("@" + _text(f["installed_version"]) if f.get("installed_version") else "")
        if f.get("fixed_version"):
            pkg += " → fixed in " + _text(f["fixed_version"])
        parts.append(pkg)
    tag = "🆕 " if f.get("diff_status") == "new" else ""
    if f.get("verdict") == "confirmed":
        tag += "🧠 "
    head = "- %s**%s** (%s) — %s" % (tag, _text(f.get("title")) or "Finding", _text(f.get("repo")), " · ".join(parts))
    lines = [head]
    if with_code and f.get("code"):
        lines.append("    " + _code(f["code"]))
    if f.get("description"):
        lines.append("    " + _text(f["description"])[:300])
    details = f.get("details") or {}
    if details:
        lines.append("    Observed: %s" % _text(details.get("observed_result"))[:300])
        lines.append("    Likelihood %s · impact %s · confidence %s" % (
            _text(details.get("likelihood")), _text(details.get("impact")), _text(details.get("confidence"))))
        lines.append("    Recommended fix (guidance only): %s" % _text(details.get("remediation"))[:300])
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
        "| Repo | Commit | Critical | High | Medium | Low | Secrets | New | Status |",
        "|------|--------|:--------:|:----:|:------:|:---:|:-------:|:---:|:------:|",
    ]
    for r in repo_summaries(findings, meta.get("repos", []), meta.get("source_refs")):
        c = r["counts"]
        out.append("| %s | %s | %d | %d | %d | %d | %d | %d | %s |" % (
            _text(r["name"]), _commit(r.get("source_ref")), c["CRITICAL"], c["HIGH"], c["MEDIUM"],
            c["LOW"] + c["INFO"], r["secrets"], r["new"], STATUS_EMOJI[r["status"]]))
    out.append("")
    out += _diff_markdown(meta.get("diff"))
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
    out += _audit_markdown(meta.get("audits") or {})
    out += _baseline_markdown(meta.get("baseline") or {})
    out += ["", "## ⏭️ Skipped", ""]
    out += ["- %s" % _text(s) for s in meta.get("skipped", [])] or ["_None._"]
    out += ["", "## 📋 Remediation guidance", "",
            "Guidance for each finding category is in `references/remediation.md` of the job-security-scan skill.",
            ""]
    return "\n".join(out)


def _commit(ref):
    if not isinstance(ref, dict) or not ref.get("commit"):
        return "—"
    return _code(ref["commit"][:10]) + (" (dirty)" if ref.get("dirty") else "")


def _diff_markdown(diff):
    if diff is None:
        return []
    if not diff.get("compared_runs"):
        return ["", "**Changes since last run:** first scan — nothing to compare with.", ""]
    out = ["", "## 🔁 Changes since last run", "",
           "🆕 new **%d** · ⏳ still open **%d** · ✅ fixed **%d**" % (diff["new"], diff["open"], diff["fixed"])
           + (" · first scan by a scanner **%d**" % diff["first_scan"] if diff.get("first_scan") else "")
           + (" · not re-checked this run **%d**" % diff["not_rechecked"] if diff.get("not_rechecked") else ""),
           "", "Compared with: %s" % ", ".join(_code(r) for r in diff["compared_runs"]), ""]
    fixed = diff.get("fixed_findings") or []
    if fixed:
        out += ["### ✅ Fixed since last run", ""]
        for f in fixed:
            loc = _code("%s:%s" % (f["file"], f["line"]) if f.get("line") else f["file"]) if f.get("file") else ""
            out.append("- ~~%s~~ (%s) — %s · %s · %s" % (
                _text(f.get("title")) or "Finding", _text(f.get("repo")), _text(f.get("severity")),
                _text(f.get("scanner")), loc))
        out.append("")
    return out


def _audit_markdown(audits):
    if not audits:
        return []
    out = ["", "## 🧠 Deep audit (agent-verified)", "",
           "Confirmed findings are listed above by severity (marked 🧠). Each was independently re-checked by a "
           "fresh agent that tried to disprove it. Needs-validation leads have no severity: a specific fact "
           "outside the source decides them.", ""]
    for repo, a in sorted(audits.items()):
        cov = a.get("coverage") or {}
        out += ["### %s" % _text(repo), "",
                "- Profile **%s** · run status **%s** · execution **%s**" % (
                    _text(a.get("profile") or "—"), _text(a.get("run_status") or "—"),
                    _text(a.get("execution_policy") or "—")),
                "- Coverage: %s" % (" · ".join("%s %d" % (_text(k), v) for k, v in sorted(cov.items())) or "—"),
                "- Confirmed **%d** · needs validation **%d** · rejected **%d**" % (
                    a.get("confirmed", 0), len(a.get("needs_validation") or []), a.get("rejected", 0))]
        if a.get("incomplete_reason"):
            out.append("- ⚠️ Incomplete: %s — a partial pass, not complete coverage" % _text(a["incomplete_reason"]))
        if a.get("errors"):
            out.append("- ⚠️ Audit output not merged: %s" % _text("; ".join(a["errors"][:3])))
        out.append("")
        if a.get("needs_validation"):
            out += ["#### Needs validation (no severity)", "",
                    "| Lead | Where | Blocker | How to resolve |", "|---|---|---|---|"]
            for n in a["needs_validation"]:
                where = _code("%s:%s" % (n["file"], n["line"])) if n.get("file") else "—"
                plan = " / ".join(_text(x) for x in (n.get("local"), n.get("deployment")) if x)
                out.append("| %s | %s | %s | %s |" % (_text(n["title"]), where, _text("; ".join(n["blockers"])),
                                                     plan))
            out.append("")
        if a.get("deferred"):
            out += ["#### Not covered this run", ""]
            out += ["- %s — %s × %s: %s" % (_text(d["status"]), _text(d["surface"]), _text(d["attack_class"]),
                                           _text(d["reason"])) for d in a["deferred"][:30]]
            out.append("")
        if a.get("hardening"):
            out += ["#### Hardening notes (not vulnerabilities)", ""]
            out += ["- %s" % _text(h) for h in a["hardening"][:30]]
            out.append("")
    return out


def _baseline_markdown(baseline):
    accepted, expired = baseline.get("accepted") or [], baseline.get("expired") or []
    unused, invalid = baseline.get("unused") or [], baseline.get("invalid") or []
    if not (accepted or expired or unused or invalid):
        return []
    out = ["", "## 🤝 Accepted findings (baseline)", "",
           "Listed in %s; not counted above." % _code(baseline.get("path") or "baseline"), ""]
    for f in accepted:
        out.append("- %s (%s) — %s · %s — accepted: %s%s" % (
            _text(f.get("title")) or "Finding", _text(f.get("repo")), _text(f.get("severity")),
            _code(f.get("fingerprint")), _text(f.get("baseline_reason")),
            (" (until %s)" % _text(f["baseline_expires"])) if f.get("baseline_expires") else ""))
    if expired:
        out += ["", "Expired entries (their findings are reported again): "
                + ", ".join(_code(e.get("fingerprint")) for e in expired)]
    if unused:
        out += ["", "Entries that matched nothing this run (fixed, or not re-checked): "
                + ", ".join(_code(u) for u in unused)]
    if invalid:
        out += ["", "Invalid entries ignored: %d (%s)" % (len(invalid), _text(invalid[0]["reason"]))]
    out.append("")
    return out
