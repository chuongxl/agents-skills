"""Accepted findings ("baseline"): a team's written decision to live with specific findings.

    {"version": 1, "entries": [{"fingerprint": "<16 hex from security-report.json>", "reason": "why",
                                "expires": "YYYY-MM-DD" (optional), "owner": "who decided" (optional)}]}

Accepted findings leave the counts and the finding sections and are listed in their own report section with the
reason, so an acceptance is always visible; an expired entry stops applying; an entry that matches nothing is
listed as unused. The baseline only hides findings from the counts - it never edits anything it scans.
Stdlib only; Python 3.8+.
"""
import json
import re
from datetime import date

FP = re.compile(r"^[0-9a-f]{16}$")


def load(path, today=None):
    """{path, active: {fingerprint: entry}, expired: [...], invalid: [...]} for a baseline file."""
    result = {"path": path, "active": {}, "expired": [], "invalid": []}
    if not path:
        return result
    try:
        with open(path, encoding="utf-8") as fh:
            doc = json.load(fh)
    except (OSError, ValueError) as exc:
        result["invalid"].append({"entry": None, "reason": "cannot read baseline: %s" % exc})
        return result
    entries = doc.get("entries") if isinstance(doc, dict) else None
    if not isinstance(entries, list):
        result["invalid"].append({"entry": None, "reason": 'baseline must be {"version": 1, "entries": [...]}'})
        return result
    today = today or date.today()
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("fingerprint"), str) \
                or not FP.match(entry["fingerprint"]) or not str(entry.get("reason") or "").strip():
            result["invalid"].append({"entry": entry, "reason": "each entry needs a 16-hex fingerprint and a reason"})
            continue
        expires = entry.get("expires")
        if expires is not None:
            try:
                if date.fromisoformat(str(expires)) < today:
                    result["expired"].append(entry)
                    continue
            except ValueError:
                result["invalid"].append({"entry": entry, "reason": "expires must be YYYY-MM-DD"})
                continue
        result["active"][entry["fingerprint"]] = entry
    return result


def split(rows, baseline):
    """(reported rows, accepted rows with their reason, unused fingerprints). Rows already have fingerprints."""
    reported, accepted, used = [], [], set()
    for row in rows:
        entry = baseline["active"].get(row["fingerprint"])
        if entry is None:
            reported.append(row)
            continue
        used.add(row["fingerprint"])
        accepted.append(dict(row, accepted_reason=str(entry["reason"]), accepted_expires=entry.get("expires"),
                             accepted_owner=entry.get("owner")))
    return reported, accepted, sorted(fp for fp in baseline["active"] if fp not in used)


def section(baseline, accepted, unused):
    """The report's `baseline` object."""
    return {"path": baseline["path"], "accepted": accepted, "unused": unused, "expired": baseline["expired"],
            "invalid": baseline["invalid"]}


# ── report section ───────────────────────────────────────────────────────────

def validate(doc, err):
    section = doc.get("baseline")
    if section is None:
        return
    if not isinstance(section, dict) or not isinstance(section.get("accepted"), list) \
            or not isinstance(section.get("unused"), list):
        err("baseline must be an object with 'accepted' and 'unused' lists")
        return
    live = set(f.get("fingerprint") for f in doc.get("findings", []) if isinstance(f, dict))
    for i, row in enumerate(section["accepted"]):
        where = "baseline.accepted[%d]" % i
        if not isinstance(row, dict) or not FP.match(str(row.get("fingerprint"))):
            err("%s: needs a 16-hex fingerprint" % where)
        elif row["fingerprint"] in live:
            err("%s: an accepted finding must not also be a reported finding" % where)
        elif not str(row.get("accepted_reason") or "").strip():
            err("%s: needs accepted_reason" % where)


def render_markdown(doc, text, code):
    section = doc.get("baseline")
    if not section:
        return []
    out = ["", "## 🤝 Accepted findings (baseline)", "",
           "Listed in %s; not counted above. Each entry says why it was accepted." % code(section.get("path") or "")
           , ""]
    for f in section["accepted"]:
        where = code("%s:%s" % (f["file"], f["line"]) if f.get("line") else f["file"]) if f.get("file") else "—"
        extra = "".join(" · %s" % text(x) for x in (f.get("accepted_owner"),
                                                    "until " + str(f["accepted_expires"]) if f.get("accepted_expires")
                                                    else None) if x)
        out.append("- **%s** (%s) — %s · %s — %s%s" % (text(f.get("title")), text(f.get("repo")), where,
                                                       code(f["fingerprint"]), text(f["accepted_reason"])[:300], extra))
    for fp in section["unused"]:
        out.append("- ⚠️ baseline entry %s matches no finding in this run" % code(fp))
    for e in section["expired"]:
        out.append("- ⚠️ baseline entry %s expired on %s and no longer applies" % (
            code(e.get("fingerprint")), text(e.get("expires"))))
    for bad in section["invalid"]:
        out.append("- ⚠️ ignored baseline entry: %s" % text(bad.get("reason")))
    out.append("")
    return out


def render_html(doc):
    import html
    section = doc.get("baseline")
    if not section:
        return ""
    e = html.escape
    items = ["<li>%s (%s) — <code>%s</code> — %s</li>" % (
        e(str(f.get("title") or "")), e(str(f.get("repo") or "")), e(str(f.get("fingerprint"))),
        e(f["accepted_reason"][:300])) for f in section["accepted"]]
    items += ["<li>⚠️ entry <code>%s</code> matches no finding in this run</li>" % e(fp) for fp in section["unused"]]
    items += ["<li>⚠️ entry <code>%s</code> expired on %s</li>" % (e(str(x.get("fingerprint"))),
                                                                  e(str(x.get("expires")))) for x in section["expired"]]
    items += ["<li>⚠️ ignored entry: %s</li>" % e(str(b.get("reason"))) for b in section["invalid"]]
    return ('<div class="runinfo" id="baseline"><div><strong>🤝 Accepted findings (baseline)</strong> — not counted '
            'above.</div><ul>%s</ul></div>' % "".join(items))
