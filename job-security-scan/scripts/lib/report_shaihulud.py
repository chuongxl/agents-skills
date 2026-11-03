"""The Shai-Hulud section of the reports: one row per target (each repo and, with --host, this machine) with the
check's verdict, what it looked at, the indicator data it used and where its raw output is.

A clean verdict is only worth something if the reader can see the check ran and what it covered, so a target
whose check failed shows "error" and a target it never ran on shows "not-run" - never silence.
Stdlib only; Python 3.8+.
"""

import html
import json
from pathlib import Path

from shaihulud.findings import redact

HOST_RESULTS = "_host"
HOST_LABEL = "this machine"
VERDICTS = ("affected", "suspicious", "clean", "error", "not-run")
EXPOSURE_RULES = ("credential-store", "credential-permissions")
MAX_BYTES = 10 * 1024 * 1024
MAX_LIST = 50
CHECKED_INT = ("ioc_packages", "packages", "installed_packages", "manifests", "install_hooks", "workflows",
               "projects", "global_packages", "python_packages", "npm_cache_entries", "credential_stores")
LABEL = {"affected": "🔴 AFFECTED", "suspicious": "🟡 SUSPICIOUS", "clean": "🟢 CLEAN", "error": "⚠️ ERROR",
         "not-run": "⏭️ not run"}
RUNBOOK = "references/remediation.md"


def _load(path):
    try:
        if path.stat().st_size > MAX_BYTES:
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) and data.get("scanner") == "shai-hulud" else None


def _checked(raw):
    """Keep only the known counters and short path lists; nothing else from the raw file reaches the report."""
    raw = raw if isinstance(raw, dict) else {}
    out = {}
    for k in CHECKED_INT:
        if isinstance(raw.get(k), int) and not isinstance(raw.get(k), bool):
            out[k] = raw[k]
    if isinstance(raw.get("ioc_version"), str):
        out["ioc_version"] = raw["ioc_version"][:40]
    files = raw.get("dependency_files")
    if isinstance(files, list):
        out["dependency_files"] = [redact(str(f))[:200] for f in files if isinstance(f, str)][:MAX_LIST]
    return out


def _error_text(path):
    try:
        text = path.read_text(encoding="utf-8", errors="replace")[:4000]
    except OSError:
        return "the check did not write a result"
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    return redact(" / ".join(lines[-3:]))[:300] if lines else "the check did not write a result"


def build(results_dir, repos):
    """The `shai_hulud` block of security-report.json for the repo result folders of one run."""
    targets, version = [], None
    for repo in repos:
        d = Path(results_dir) / repo
        host = repo == HOST_RESULTS
        t = {"repo": HOST_LABEL if host else repo, "mode": "host" if host else "repo", "verdict": "not-run",
             "checked": {}, "counts": {}, "raw": None, "error": None, "credential_stores": []}
        data = _load(d / "shai-hulud.json") if (d / "shai-hulud.json").is_file() else None
        txt = d / "shai-hulud.txt"
        if data is not None and data.get("verdict") in ("affected", "suspicious", "clean"):
            t["verdict"] = data["verdict"]
            t["checked"] = _checked(data.get("checked"))
            counts = data.get("counts") if isinstance(data.get("counts"), dict) else {}
            t["counts"] = dict((str(k), v) for k, v in counts.items() if isinstance(v, int) and v)
            t["raw"] = "%s/%s" % (repo, "shai-hulud.txt" if txt.is_file() else "shai-hulud.json")
            if host:
                t["credential_stores"] = sorted({redact(str(f.get("location", "")))[:200]
                                                 for f in data.get("findings", []) if isinstance(f, dict)
                                                 and f.get("category") == "credential-store"})[:MAX_LIST]
            version = version or t["checked"].get("ioc_version") or (str(data.get("ioc_version") or "")[:40] or None)
        elif (d / "shai-hulud.json").is_file() or txt.is_file():
            t["verdict"] = "error"
            t["error"] = _error_text(txt) if txt.is_file() else "unreadable shai-hulud.json"
            t["raw"] = "%s/%s" % (repo, "shai-hulud.txt" if txt.is_file() else "shai-hulud.json")
        targets.append(t)
    return {"ran": any(t["verdict"] != "not-run" for t in targets), "ioc_version": version, "targets": targets}


def validate(doc, err):
    """Report-validator rules for the block (called from report_schema)."""
    sh = doc.get("shai_hulud")
    if not isinstance(sh, dict) or not isinstance(sh.get("targets"), list) or not isinstance(sh.get("ran"), bool):
        err("shai_hulud: must be an object with 'ran' (true/false) and 'targets' (list)")
        return
    partial = bool((doc.get("run") or {}).get("partial"))
    by_repo = {}
    held = list(doc.get("findings", [])) + list((doc.get("baseline") or {}).get("accepted") or [])
    for f in held:     # an accepted (baseline) finding still makes the verdict true
        if isinstance(f, dict) and f.get("scanner") == "shai-hulud" and f.get("rule_id") not in EXPOSURE_RULES:
            by_repo.setdefault(f.get("repo"), []).append(f)
    for i, t in enumerate(sh["targets"]):
        where = "shai_hulud.targets[%d]" % i
        if not isinstance(t, dict):
            err("%s: must be an object" % where)
            continue
        v = t.get("verdict")
        if v not in VERDICTS:
            err("%s: verdict must be one of %s" % (where, ", ".join(VERDICTS)))
            continue
        if not isinstance(t.get("checked"), dict):
            err("%s: checked must be an object" % where)
        found = by_repo.get(t.get("repo"), [])
        if v == "clean" and found:
            err("%s: verdict clean but %d Shai-Hulud finding(s) for %s" % (where, len(found), t.get("repo")))
        if v in ("affected", "suspicious") and not found and not partial:
            err("%s: verdict %s but no Shai-Hulud finding for %s" % (where, v, t.get("repo")))
        if v == "error" and not t.get("error"):
            err("%s: error verdict needs the error message" % where)
    if sh["ran"] != any(isinstance(t, dict) and t.get("verdict") != "not-run" for t in sh["targets"]):
        err("shai_hulud: 'ran' does not match the targets")


# ── rendering ────────────────────────────────────────────────────────────────

def _plural(n, word):
    return "%d %s%s" % (n, word, "" if n == 1 else "s")


def checked_text(t):
    """One line saying what the check looked at for a target."""
    c = t.get("checked") or {}
    if t["verdict"] in ("error", "not-run"):
        return ""
    files = c.get("dependency_files") or []
    if t["mode"] == "host":
        parts = [_plural(c.get("projects", 0), "project"), _plural(c.get("packages", 0), "package"),
                 _plural(c.get("global_packages", 0), "global install"),
                 _plural(c.get("python_packages", 0), "Python package"),
                 _plural(c.get("npm_cache_entries", 0), "npm cache entry").replace("entrys", "entries"),
                 _plural(c.get("credential_stores", 0), "credential store")]
        return ", ".join(parts)
    if not c.get("packages") and not c.get("manifests") and not files:
        return "nothing to check (no lockfile, requirements file or package.json)"
    shown = ", ".join(files[:3]) + (" +%d more" % (len(files) - 3) if len(files) > 3 else "")
    parts = ["%s (%s)" % (_plural(len(files), "dependency file"), shown) if files else "0 dependency files",
             _plural(c.get("packages", 0), "package"), _plural(c.get("manifests", 0), "package.json"),
             _plural(c.get("install_hooks", 0), "install hook"), _plural(c.get("workflows", 0), "workflow")]
    if c.get("installed_packages"):
        parts.insert(2, "%d installed" % c["installed_packages"])
    return ", ".join(parts).replace("package.jsons", "package.json files")


def verdict_text(t):
    counts = t.get("counts") or {}
    detail = ", ".join("%d %s" % (n, s.lower()) for s, n in sorted(counts.items(),
                       key=lambda kv: ("CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO").index(kv[0])
                       if kv[0] in ("CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO") else 9))
    if t["verdict"] == "affected":
        return "%s — %s; follow the 'If affected' runbook in %s" % (LABEL["affected"], detail or "known indicator",
                                                                   RUNBOOK)
    if t["verdict"] == "suspicious":
        return "%s — %s" % (LABEL["suspicious"], detail or "worm-like install behaviour")
    if t["verdict"] == "error":
        return "%s — %s" % (LABEL["error"], t.get("error") or "")
    return LABEL[t["verdict"]]


def render_markdown(doc, text, code):
    """Markdown lines of the section. `text` and `code` are report_formats' escapers."""
    sh = doc.get("shai_hulud") or {"ran": False, "targets": []}
    out = ["", "## 🪱 Shai-Hulud check", ""]
    if not sh.get("ran"):
        return out + ["_The Shai-Hulud check did not run in this scan (it runs in every profile, with "
                      "`--scanner shai-hulud` and with `--host`)._"]
    c = [t for t in sh["targets"] if t.get("checked")]
    known = c[0]["checked"].get("ioc_packages") if c else None
    out += ["Indicator data: %s%s. A verdict covers only what is listed as checked." % (
        code(sh.get("ioc_version") or "unknown"), " (%d known compromised releases)" % known if known else ""), "",
        "| Target | Verdict | Checked | Raw output |", "|---|---|---|---|"]
    for t in sh["targets"]:
        out.append("| %s | %s | %s | %s |" % (text(t["repo"]), text(verdict_text(t)), text(checked_text(t)) or "—",
                                             code(t["raw"]) if t.get("raw") else "—"))
    for t in sh["targets"]:
        if t.get("credential_stores"):
            out += ["", "Credential stores to rotate if %s is affected (values never read): %s" % (
                text(t["repo"]), ", ".join(code(s) for s in t["credential_stores"]))]
    if doc.get("run", {}).get("partial"):
        out += ["", "_Partial run: verdicts cover the whole repo; findings outside the changed files are not listed._"]
    return out


def render_html(doc):
    sh = doc.get("shai_hulud") or {"ran": False, "targets": []}
    e = html.escape
    if not sh.get("ran"):
        return ('<div class="runinfo" id="shai-hulud"><strong>🪱 Shai-Hulud check:</strong> did not run in this '
                'scan.</div>')
    rows = []
    for t in sh["targets"]:
        raw = '<a href="%s">%s</a>' % (e(t["raw"]), e(t["raw"])) if t.get("raw") else "—"
        rows.append('<tr class="sh-%s"><td><code>%s</code></td><td>%s</td><td>%s</td><td>%s</td></tr>' % (
            e(t["verdict"]), e(t["repo"]), e(verdict_text(t)), e(checked_text(t)) or "—", raw))
    creds = "".join("<div>Credential stores to rotate if %s is affected: %s</div>" % (
        e(t["repo"]), ", ".join("<code>%s</code>" % e(s) for s in t["credential_stores"]))
        for t in sh["targets"] if t.get("credential_stores"))
    return ('<div class="runinfo" id="shai-hulud"><div><strong>🪱 Shai-Hulud check</strong> — indicator data '
            '<code>%s</code>. A verdict covers only what is listed as checked.</div>'
            '<table class="sh-table"><thead><tr><th>Target</th><th>Verdict</th><th>Checked</th><th>Raw output</th>'
            '</tr></thead><tbody>%s</tbody></table>%s</div>' % (e(sh.get("ioc_version") or "unknown"),
                                                               "".join(rows), creds))
