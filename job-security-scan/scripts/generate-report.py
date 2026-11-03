#!/usr/bin/env python3
"""
generate-report.py — Generate the security reports (Markdown, JSON, HTML) for one scan run.

Usage:
  python3 generate-report.py --results-dir DIR --config repository.md --out-dir DIR
                             [--repos-root PATH] [--home PATH] [--workspace PATH]
  python3 generate-report.py --results-dir DIR --config repository.md --output report.html   (HTML only)

Every finding is located to file + line + one line of code (secrets: file + line only).
The reports describe findings; they never change code.

Reads JSON output from all scanners under results-dir/{repo}/ and produces
a single self-contained HTML file with:
  - Summary cards per severity
  - Findings table with VS Code deep-links (file:line)
  - Filter by repo, scanner, severity
  - Package name + CVE ID for dependency findings
  - Remediation links
"""

import json
import os
import re
import sys
import argparse
import html
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))

import report_formats  # noqa: E402
import report_locate   # noqa: E402
import report_model    # noqa: E402
import report_schema   # noqa: E402
import report_scope    # noqa: E402
import report_shaihulud  # noqa: E402
import report_audit    # noqa: E402


# ─── Config Parser ────────────────────────────────────────────────────────────

def parse_config(config_path):
    """Parse repository.md frontmatter into a dict."""
    text = Path(config_path).read_text()
    match = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    if not match:
        return {}
    cfg = {}
    for line in match.group(1).splitlines():
        if ":" in line and not line.strip().startswith("#") and not line.startswith(" "):
            k, _, v = line.partition(":")
            v = re.sub(r'\s+#.*$', '', v).strip().strip('"').strip("'")
            if v:
                cfg[k.strip()] = v
    return cfg


# ─── Scanner Parsers ──────────────────────────────────────────────────────────

def severity_order(sev):
    return {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "INFO": 4, "UNKNOWN": 5}.get(sev.upper(), 5)


def parse_trivy(repo, results_dir, workspace):
    """Parse trivy JSON output."""
    findings = []
    json_path = Path(results_dir) / repo / "trivy.json"
    if not json_path.exists():
        return findings

    try:
        data = json.loads(json_path.read_text())
    except Exception:
        return findings

    for result in data.get("Results", []):
        target = result.get("Target", "")
        # Vulnerabilities (package CVEs)
        for v in result.get("Vulnerabilities", []):
            findings.append({
                "repo": repo,
                "scanner": "trivy",
                "type": "vulnerability",
                "severity": v.get("Severity", "UNKNOWN").upper(),
                "file": target,
                "line": None,
                "package": v.get("PkgName", ""),
                "installed_version": v.get("InstalledVersion", ""),
                "fixed_version": v.get("FixedVersion", ""),
                "rule_id": v.get("VulnerabilityID", ""),
                "title": v.get("Title", v.get("VulnerabilityID", "")),
                "description": v.get("Description", "")[:300],
                "url": v.get("PrimaryURL", ""),
                "workspace": workspace,
            })
        # Misconfigurations
        for m in result.get("Misconfigurations", []):
            cause = m.get("CauseMetadata", {})
            line = cause.get("StartLine") or cause.get("EndLine")
            findings.append({
                "repo": repo,
                "scanner": "trivy",
                "type": "misconfig",
                "severity": m.get("Severity", "UNKNOWN").upper(),
                "file": target,
                "line": line,
                "package": "",
                "installed_version": "",
                "fixed_version": m.get("Resolution", ""),
                "rule_id": m.get("ID", ""),
                "title": m.get("Title", ""),
                "description": m.get("Message", ""),
                "url": m.get("PrimaryURL", ""),
                "workspace": workspace,
            })
        # Secrets
        for s in result.get("Secrets", []):
            findings.append({
                "repo": repo,
                "scanner": "trivy",
                "type": "secret",
                "severity": "CRITICAL",
                "file": target,
                "line": s.get("StartLine"),
                "package": "",
                "installed_version": "",
                "fixed_version": "",
                "rule_id": s.get("RuleID", ""),
                "title": s.get("Title", "Secret detected"),
                "description": s.get("Category", ""),
                "url": "",
                "workspace": workspace,
            })
    return findings


def parse_gitleaks(repo, results_dir, workspace):
    """Parse gitleaks JSON output."""
    findings = []
    json_path = Path(results_dir) / repo / "gitleaks.json"
    if not json_path.exists():
        return findings
    try:
        data = json.loads(json_path.read_text())
        if not isinstance(data, list):
            return findings
    except Exception:
        return findings

    for item in data:
        findings.append({
            "repo": repo,
            "scanner": "gitleaks",
            "type": "secret",
            "severity": "CRITICAL",
            "file": item.get("File", ""),
            "line": item.get("StartLine"),
            "package": "",
            "installed_version": "",
            "fixed_version": "",
            "rule_id": item.get("RuleID", ""),
            "title": item.get("Description", "Secret detected"),
            "description": f"Commit: {item.get('Commit','')[:8]} · Match: [REDACTED]",
            "url": "",
            "workspace": workspace,
        })
    return findings


def _semgrep_is_secret(item):
    """Secret-detection rules (p/secrets, *.secrets.* ids, or metadata saying so) are reported like other
    secrets: file and line, never the matched line, which holds the secret."""
    check_id = str(item.get("check_id", "")).lower()
    if ".secrets." in check_id or check_id.startswith("secrets.") or "hardcoded-secret" in check_id:
        return True
    meta = (item.get("extra") or {}).get("metadata") or {}
    tags = []
    for key in ("category", "subcategory", "technology", "cwe"):
        v = meta.get(key)
        tags += v if isinstance(v, list) else [v]
    return any(isinstance(t, str) and ("secret" in t.lower() or "CWE-798" in t) for t in tags)


def parse_semgrep(repo, results_dir, workspace):
    """Parse semgrep JSON output."""
    findings = []
    json_path = Path(results_dir) / repo / "semgrep.json"
    if not json_path.exists():
        return findings
    try:
        data = json.loads(json_path.read_text())
    except Exception:
        return findings

    sev_map = {"ERROR": "HIGH", "WARNING": "MEDIUM", "INFO": "LOW"}
    for item in data.get("results", []):
        raw_sev = item.get("extra", {}).get("severity", "WARNING")
        findings.append({
            "repo": repo,
            "scanner": "semgrep",
            "type": "secret" if _semgrep_is_secret(item) else "sast",
            "severity": sev_map.get(raw_sev.upper(), "MEDIUM"),
            "file": item.get("path", ""),
            "line": item.get("start", {}).get("line"),
            "package": "",
            "installed_version": "",
            "fixed_version": "",
            "rule_id": item.get("check_id", ""),
            "title": item.get("check_id", "").split(".")[-1].replace("-", " ").title(),
            "description": item.get("extra", {}).get("message", "")[:300],
            "url": item.get("extra", {}).get("metadata", {}).get("references", [""])[0]
                   if item.get("extra", {}).get("metadata", {}).get("references") else "",
            "workspace": workspace,
        })
    return findings


def parse_hadolint(repo, results_dir, workspace):
    """Parse hadolint text output (format: file:line code level: message)."""
    findings = []
    txt_path = Path(results_dir) / repo / "hadolint.txt"
    if not txt_path.exists():
        return findings

    pattern = re.compile(r"^(.+?):(\d+)\s+(DL\d+|SC\d+)\s+(\w+):\s+(.+)$")
    sev_map = {"error": "HIGH", "warning": "MEDIUM", "info": "LOW", "style": "LOW"}
    for line in txt_path.read_text().splitlines():
        m = pattern.match(line.strip())
        if m:
            filepath, lineno, rule_id, level, message = m.groups()
            findings.append({
                "repo": repo,
                "scanner": "hadolint",
                "type": "misconfig",
                "severity": sev_map.get(level.lower(), "MEDIUM"),
                "file": os.path.relpath(filepath, workspace) if os.path.isabs(filepath) else filepath,
                "line": int(lineno),
                "package": "",
                "installed_version": "",
                "fixed_version": "",
                "rule_id": rule_id,
                "title": message[:120],
                "description": message,
                "url": f"https://github.com/hadolint/hadolint/wiki/{rule_id}" if rule_id.startswith("DL") else "",
                "workspace": workspace,
            })
    return findings


_GHSA_LABELS = {"CRITICAL": "CRITICAL", "HIGH": "HIGH", "MODERATE": "MEDIUM", "MEDIUM": "MEDIUM", "LOW": "LOW"}


def _score_to_severity(score):
    if score >= 9.0:
        return "CRITICAL"
    if score >= 7.0:
        return "HIGH"
    if score >= 4.0:
        return "MEDIUM"
    return "LOW"


def _osv_group_scores(groups):
    """{vuln id or alias: numeric max_severity} from osv-scanner's groups (v1.x and v2)."""
    out = {}
    for g in groups if isinstance(groups, list) else []:
        if not isinstance(g, dict):
            continue
        try:
            score = float(g.get("max_severity") or "")
        except (TypeError, ValueError):
            continue
        for ident in g.get("ids") or []:
            out[ident] = score
    return out


def _osv_severity(vuln, group_scores):
    """Severity from osv-scanner's numeric group score, else a numeric CVSS score, else the advisory's own
    label (GHSA database_specific.severity), else MEDIUM. CVSS vectors ('CVSS:3.1/AV:N/...') are not scores."""
    for ident in [vuln.get("id")] + list(vuln.get("aliases") or []):
        if ident in group_scores:
            return _score_to_severity(group_scores[ident])
    for entry in vuln.get("severity") if isinstance(vuln.get("severity"), list) else []:
        try:
            return _score_to_severity(float(str(entry.get("score", ""))))
        except (AttributeError, TypeError, ValueError):
            continue
    label = str((vuln.get("database_specific") or {}).get("severity", "")).upper() \
        if isinstance(vuln.get("database_specific"), dict) else ""
    return _GHSA_LABELS.get(label, "MEDIUM")


def parse_osv(repo, results_dir, workspace):
    """Parse osv-scanner JSON output."""
    findings = []
    json_path = Path(results_dir) / repo / "osv.json"
    if not json_path.exists():
        return findings
    try:
        data = json.loads(json_path.read_text())
    except Exception:
        return findings

    for result in data.get("results", []):
        source = result.get("source", {}).get("path", "yarn.lock")
        for pkg in result.get("packages", []):
            pkg_info = pkg.get("package", {})
            group_scores = _osv_group_scores(pkg.get("groups"))
            for vuln in pkg.get("vulnerabilities", []):
                sev = _osv_severity(vuln, group_scores)
                findings.append({
                    "repo": repo,
                    "scanner": "osv",
                    "type": "vulnerability",
                    "severity": sev,
                    "file": source,
                    "line": None,
                    "package": pkg_info.get("name", ""),
                    "installed_version": pkg_info.get("version", ""),
                    "fixed_version": "",
                    "rule_id": vuln.get("id", ""),
                    "title": vuln.get("summary", vuln.get("id", "")),
                    "description": (vuln.get("details", "") or "")[:300],
                    "url": f"https://osv.dev/vulnerability/{vuln.get('id','')}",
                    "workspace": workspace,
                })
    return findings


def parse_trufflehog(repo, results_dir, workspace):
    """Parse trufflehog JSONL output."""
    findings = []
    json_path = Path(results_dir) / repo / "trufflehog.json"
    if not json_path.exists():
        return findings

    for raw_line in json_path.read_text().splitlines():
        raw_line = raw_line.strip()
        if not raw_line:
            continue
        try:
            item = json.loads(raw_line)
        except Exception:
            continue
        verified = item.get("Verified", False)
        git_data = item.get("SourceMetadata", {}).get("Data", {}).get("Git", {})
        findings.append({
            "repo": repo,
            "scanner": "trufflehog",
            "type": "secret",
            "severity": "CRITICAL" if verified else "HIGH",
            "file": git_data.get("file", ""),
            "line": git_data.get("line"),
            "package": "",
            "installed_version": "",
            "fixed_version": "",
            "rule_id": item.get("DetectorName", ""),
            "title": f"{'✅ VERIFIED ACTIVE' if verified else 'Unverified'} secret — {item.get('DetectorName','')}",
            "description": f"Commit: {git_data.get('commit','')[:8]} · Detector: {item.get('DetectorName','')} · [value REDACTED]",
            "url": "",
            "workspace": workspace,
        })
    return findings


# ─── Collect All Findings ─────────────────────────────────────────────────────

def parse_advisories(repo, results_dir, workspace):
    """Parse match.py output (vendor-first advisory engine)."""
    findings = []
    json_path = Path(results_dir) / repo / "advisories.json"
    if not json_path.exists():
        return findings
    try:
        data = json.loads(json_path.read_text())
    except Exception:
        return findings
    labels = {
        "affected": "Affected",
        "possibly-affected": "Possibly affected (version not pinned)",
        "affected-end-of-life": "Affected (end-of-life line)",
        "affected-if-condition-holds": "Affected if condition holds",
        "end-of-life": "End-of-life runtime line",
        "unpinned": "Runtime not pinned to a patch version",
        "pending": "Vendor pre-announcement (details pending)",
        "unknown-version": "Version unknown",
    }
    for f in data.get("findings", []):
        sev = f.get("severity", "unknown").upper()
        if f.get("state") == "pending":
            sev = "LOW"
        elif sev == "UNKNOWN":
            sev = "MEDIUM"
        note = labels.get(f.get("state"), f.get("state", ""))
        if f.get("unmet_conditions"):
            note += ": " + ", ".join("%s=%s" % (c["type"], c["value"]) for c in f["unmet_conditions"])
        if f.get("exploited"):
            note += " | actively exploited (CISA KEV)"
        if f.get("conflicts"):
            note += " | sources disagree on the fixed version"
        src = f.get("source", {})
        findings.append({
            "repo": repo,
            "scanner": "advisory",
            "type": "vulnerability",
            "severity": sev,
            "file": f.get("location") or f.get("component", ""),
            "line": None,
            "package": f.get("component", ""),
            "installed_version": f.get("installed") or "",
            "fixed_version": f.get("fixed_in") or "",
            "rule_id": f.get("id", ""),
            "title": f.get("title", ""),
            "description": ("%s - source: %s (%s)" % (note, src.get("vendor", ""), src.get("tier", "")))[:300],
            "url": src.get("url", ""),
            "workspace": workspace,
        })
    return findings


HOST_RESULTS = "_host"        # run-scan.sh --host writes here
HOST_LABEL = "this machine"


def parse_shai_hulud(repo, results_dir, workspace):
    """Parse shai-hulud-scan.py JSON (repo mode, or host mode under _host/)."""
    findings = []
    json_path = Path(results_dir) / repo / "shai-hulud.json"
    if not json_path.exists():
        return findings
    try:
        data = json.loads(json_path.read_text())
    except Exception:
        return findings
    tier_label = {"affected": "AFFECTED", "suspicious": "Suspicious", "exposure": "Rotate if affected"}
    for f in data.get("findings", []):
        sev = f.get("severity", "LOW").upper()
        if sev == "INFO":
            sev = "LOW"
        parts = [tier_label.get(f.get("tier"), f.get("tier", ""))]
        if f.get("wave"):
            parts.append("wave " + f["wave"])
        if f.get("evidence"):
            parts.append("evidence: " + f["evidence"])
        if f.get("remediation"):
            parts.append(f["remediation"])
        findings.append({
            "repo": HOST_LABEL if repo == HOST_RESULTS else repo,
            "scanner": "shai-hulud",
            "type": "supply-chain",
            "severity": sev,
            "file": f.get("location", ""),
            "line": None,
            "package": f.get("package", ""),
            "installed_version": f.get("version", ""),
            "fixed_version": "",
            "rule_id": f.get("category", ""),
            "title": f.get("title", ""),
            "description": " - ".join(parts)[:300],
            "url": "",
            "evidence": f.get("evidence", ""),
            "workspace": workspace,
        })
    return findings


def parse_code_audit(repo, results_dir, workspace):
    """Candidates from the agent-driven code audit (audit.py collect writes <repo>/code-audit.json)."""
    path = Path(results_dir) / repo / "code-audit.json"
    if not path.is_file() or path.stat().st_size > 5 * 1024 * 1024:
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    out = []
    for c in data.get("candidates", []) if isinstance(data, dict) else []:
        if not isinstance(c, dict):
            continue
        sev = c.get("severity") if c.get("severity") in ("CRITICAL", "HIGH", "MEDIUM", "LOW") else "MEDIUM"
        out.append({
            "repo": repo, "scanner": "code-audit", "type": "secret" if c.get("type") == "secret" else "sast",
            "severity": sev, "file": str(c.get("file") or ""), "line": c.get("line") if isinstance(c.get("line"), int) else None,
            "package": "", "installed_version": "", "fixed_version": "",
            "rule_id": "code-audit", "title": str(c.get("title") or "")[:160],
            "description": ("[%s] %s - %s" % (", ".join(str(x) for x in (c.get("attack_classes") or [c.get("attack_class")]) if x),
                                              c.get("boundary") or "", c.get("root_cause") or ""))[:300],
            "url": "", "workspace": workspace,
        })
    return out


def collect_findings(results_dir, repos, workspace):
    parsers = [parse_gitleaks, parse_trufflehog, parse_trivy, parse_semgrep, parse_hadolint, parse_osv,
               parse_advisories, parse_shai_hulud, parse_code_audit]
    all_findings = []
    for repo in repos:
        for parser in parsers:
            try:
                all_findings.extend(parser(repo, results_dir, workspace))
            except Exception as exc:  # one unexpected tool output must not cost the whole report
                sys.stderr.write("  warning: %s could not read %s output: %s: %s\n"
                                 % (parser.__name__, repo, type(exc).__name__, exc))
    all_findings.sort(key=lambda f: (severity_order(f["severity"]), f["repo"], f["scanner"]))
    return all_findings


# ─── File Link Builder ────────────────────────────────────────────────────────

def file_link(finding, org, repo_name):
    """Build a VS Code deep-link for the finding's file + line."""
    f = finding["file"]
    line = finding["line"]
    workspace = finding.get("workspace", ".")

    if not f:
        return ""

    # Absolute path for vscode:// link
    abs_path = os.path.join(workspace, repo_name, f) if not os.path.isabs(f) else f

    if line:
        vscode_url = f"vscode://file{abs_path}:{line}"
        label = html.escape(f"{f}:{line}")
    else:
        vscode_url = f"vscode://file{abs_path}"
        label = html.escape(f)

    return f'<a href="{html.escape(vscode_url)}" class="file-link" title="Open in VS Code">📄 {label}</a>'


def cve_link(rule_id, url):
    """Build a link to CVE/advisory detail."""
    if not rule_id:
        return ""
    display = html.escape(rule_id)
    if url:
        return f'<a href="{html.escape(url)}" target="_blank" class="cve-link">{display} ↗</a>'
    if rule_id.startswith("CVE-"):
        nvd_url = f"https://nvd.nist.gov/vuln/detail/{rule_id}"
        return f'<a href="{html.escape(nvd_url)}" target="_blank" class="cve-link">{display} ↗</a>'
    return f'<span class="rule-id">{display}</span>'


# ─── HTML Template ────────────────────────────────────────────────────────────
# CSS and JS now live in assets/report-template.html — edit that file to
# customise the report's look & feel without touching Python.

SCRIPT_DIR    = Path(__file__).parent.resolve()
TEMPLATE_PATH = SCRIPT_DIR.parent / "assets" / "report-template.html"


def _runinfo_html(doc):
    run = doc.get("run") or {}
    ver = doc.get("verification") or {}
    e = html.escape
    scope = ("partial — files changed since <code>%s</code>" % e(run["since"])) if run.get("since") else "full"
    parts = ['<div class="runinfo">',
             "<div><strong>Profile:</strong> %s · <strong>Scope:</strong> %s</div>" % (e(str(run.get("profile"))), scope),
             "<div><strong>Verification:</strong> %d queued · %d pending · %d confirmed · %d need validation · "
             "%d dismissed</div>" % (ver.get("queued", 0), ver.get("pending", 0), ver.get("confirmed", 0),
                                     ver.get("needs_validation", 0), ver.get("rejected", 0))]
    if run.get("previous_run"):
        rows = doc["findings"]
        new = sum(1 for f in rows if f.get("change") == "new")
        parts.append("<div><strong>Changes since last run</strong> (<code>%s</code>): %d new · %d unchanged · "
                     "%d fixed</div>" % (e(run["previous_run"]), new, len(rows) - new, len(doc.get("fixed", []))))
        if run.get("partial"):
            parts.append("<div><em>Partial run: fixed findings are not worked out.</em></div>")
        elif doc.get("fixed"):
            parts.append("<ul>" + "".join(
                "<li>✔️ %s (%s) — <code>%s</code> · %s</li>" % (e(f.get("title") or "Finding"), e(f.get("repo") or ""),
                                                               e(f.get("file") or ""), e(f.get("rule_id") or ""))
                for f in doc["fixed"]) + "</ul>")
    else:
        parts.append("<div><strong>Changes since last run:</strong> no earlier run to compare with.</div>")
    parts.append("</div>")
    return "\n".join(parts)


def _verdict_html(f):
    v = f.get("verdict")
    if not v:
        return ""
    d = f.get("verdict_detail") or {}
    text = {"confirmed": d.get("evidence"), "needs_validation": "blocker: %s" % (d.get("blocker") or ""),
            "rejected": d.get("reason")}[v]
    label = report_formats.VERDICT_LABEL[v] + (" (carried)" if f.get("carried") else "")
    return '<span class="verdict %s">%s — %s</span>' % (html.escape(v), html.escape(label), html.escape(str(text or ""))[:400])


def build_html(doc, config, results_dir, output_path, org, workspace="."):
    """Render the HTML report from the v2 document (the same data as security-report.json)."""
    team = config.get("team", "unknown")
    scan_time = doc.get("generated_at") or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    findings = [f for f in doc["findings"] if not report_model.is_pending_audit(f)]   # pending: Code audit panel
    active = [f for f in findings if f.get("verdict") != "rejected"]

    counts = doc["counts"]
    repos   = sorted(set(f["repo"] for f in findings))
    scanners = sorted(set(f["scanner"] for f in findings))
    types   = sorted(set(f["type"] for f in findings))
    total = sum(counts.values())

    # ── Summary cards ─────────────────────────────────────────────────────────
    def card(cls, count, label):
        return f'<div class="card {cls}"><div class="card-count">{count}</div><div class="card-label">{label}</div></div>'

    if total == 0:
        cards_html = card("clean", "✅", "All Clean")
    else:
        cards_html = "".join([
            card("critical", counts["CRITICAL"], "Critical"),
            card("high",     counts["HIGH"],     "High"),
            card("medium",   counts["MEDIUM"],   "Medium"),
            card("low",      counts["LOW"],       "Low"),
            f'<div class="card" style="margin-left:auto"><div class="card-count" style="color:var(--text2)">{total}</div><div class="card-label">Total</div></div>',
        ])

    # ── Filter dropdowns ───────────────────────────────────────────────────────
    def options(items, label):
        opts = f'<option value="">{label}</option>'
        opts += "".join(f'<option value="{html.escape(i)}">{html.escape(i)}</option>' for i in items)
        return opts

    present = set(report_formats.effective_severity(f) for f in findings)
    sev_order_list = [s for s in ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"] if s in present]

    filters_html = f"""
    <div class="filters">
      <label>Severity</label>
      <select id="f-sev">{options(sev_order_list, "All severities")}</select>
      <label>Repo</label>
      <select id="f-repo">{options(repos, "All repos")}</select>
      <label>Scanner</label>
      <select id="f-scan">{options(scanners, "All scanners")}</select>
      <label>Type</label>
      <select id="f-type">{options(types, "All types")}</select>
      <button class="btn-reset" onclick="resetFilters()">Reset</button>
      <span class="filter-count" id="visible-count">{len(findings)} findings</span>
    </div>"""

    # ── Table rows ─────────────────────────────────────────────────────────────
    rows_html = ""
    if not active:
        rows_html = '<tr><td colspan="7" class="empty"><div class="icon">🟢</div>No findings — all repos are clean!</td></tr>'
    for f in sorted(findings, key=lambda x: (x.get("verdict") == "rejected",
                                             severity_order(report_formats.effective_severity(x)))):
        f = dict(f, workspace=workspace)
        sev   = report_formats.effective_severity(f)
        tool_sev = (f.get("severity") or "").upper()
        repo  = f["repo"]
        scan  = f["scanner"]
        ftype = f["type"]

        # Package cell
        pkg_parts = []
        if f.get("package"):
            pkg_parts.append(f'<div class="pkg-name">{html.escape(f["package"])}</div>')
        if f.get("installed_version"):
            pkg_parts.append(f'<div class="pkg-version">installed: {html.escape(f["installed_version"])}</div>')
        if f.get("fixed_version"):
            pkg_parts.append(f'<div class="pkg-fix">→ fix: {html.escape(f["fixed_version"])}</div>')
        pkg_html = "\n".join(pkg_parts) or '<span style="color:var(--text3)">—</span>'

        # File link cell (secret rows never carry code)
        file_html = file_link(f, org, repo) or '<span style="color:var(--text3)">—</span>'
        if f.get("code") and ftype != "secret":
            file_html += f'<div class="code-excerpt"><code>{html.escape(f["code"])}</code></div>'

        id_html = cve_link(f.get("rule_id"), f.get("url")) or '<span style="color:var(--text3)">—</span>'

        desc = html.escape((f.get("description") or "")[:200])
        title_txt = html.escape((f.get("title") or "")[:100])
        sev_extra = ""
        if f.get("change") == "new":
            sev_extra += '<br><span class="badge-new">NEW</span>'
        if sev != tool_sev:
            sev_extra += f'<span class="tool-sev">tool: {html.escape(tool_sev)}</span>'
        row_cls = ' class="dismissed"' if f.get("verdict") == "rejected" else ""

        rows_html += f"""
        <tr{row_cls} data-sev="{html.escape(sev)}" data-repo="{html.escape(repo)}" data-scan="{html.escape(scan)}" data-type="{html.escape(ftype)}">
          <td class="sev-col"><span class="badge {html.escape(sev)}">{html.escape(sev)}</span>{sev_extra}</td>
          <td class="repo-col"><code style="font-size:12px">{html.escape(repo)}</code></td>
          <td class="scanner-col"><span class="chip {html.escape(scan)}">{html.escape(scan)}</span></td>
          <td class="file-col">{file_html}</td>
          <td class="pkg-col">{pkg_html}</td>
          <td class="id-col">{id_html}</td>
          <td class="desc-col"><strong style="color:var(--text)">{title_txt}</strong><br><small>{desc}</small>{_verdict_html(f)}</td>
        </tr>"""

    # ── Render template ────────────────────────────────────────────────────────
    if not TEMPLATE_PATH.exists():
        raise FileNotFoundError(f"Template not found: {TEMPLATE_PATH}")

    title = f"Security Scan — {html.escape(team)} / {html.escape(org)}"
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    # The template's header comment documents the placeholders; fill only the markup after it, or every row
    # (and its code excerpt) would also be written into that comment.
    cut = template.find("-->") + 3 if template.lstrip().startswith("<!DOCTYPE html>\n<!--") else 0
    head, page = template[:cut], template[cut:]
    page = (page
            .replace("{{TITLE}}",       title)
            .replace("{{TEAM}}",        html.escape(team))
            .replace("{{ORG}}",         html.escape(org))
            .replace("{{SCAN_TIME}}",   html.escape(scan_time))
            .replace("{{RESULTS_DIR}}", html.escape(str(results_dir)))
            .replace("{{REPO_COUNT}}",  str(len(doc.get("repos", []))))
            .replace("{{SCANNERS}}",    html.escape(", ".join(doc.get("scanners") or scanners) or "—"))
            .replace("{{TOTAL}}",       str(total))
            .replace("{{CARDS}}",       cards_html)
            .replace("{{RUNINFO}}",     _runinfo_html(doc))
            .replace("{{SHAIHULUD}}",   report_shaihulud.render_html(doc))
            .replace("{{CODEAUDIT}}",   report_audit.render_html(doc))
            .replace("{{FILTERS}}",     filters_html)
            .replace("{{ROWS}}",        rows_html))

    Path(output_path).write_text(head + page, encoding="utf-8")
    print(f"  📄 HTML report → {output_path}")
    return output_path


def write_reports(doc, config, out_dir, results_dir=None):
    """Write security-report.{json,md,html} for a v2 document, validate the JSON and return the paths.
    Used by this script and by triage.py apply (which regenerates the reports after verification)."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    org = config.get("org", "unknown")
    run = doc.get("run") or {}
    workspace = run.get("repos_root") or run.get("workspace") or "."   # file links: <repos root>/<repo>/<file>
    paths = [out_dir / "security-report.md", out_dir / "security-report.json", out_dir / "security-report.html"]
    paths[1].write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    paths[0].write_text(report_formats.render_markdown(doc), encoding="utf-8")
    build_html(doc, config, results_dir or out_dir, str(paths[2]), org, workspace)
    errors = report_schema.validate(doc)
    if errors:
        sys.stderr.write("  warning: security-report.json failed validation:\n%s\n"
                         % "\n".join("    - " + e for e in errors[:20]))
    return paths, errors


# ─── Main ─────────────────────────────────────────────────────────────────────

def discover_repos(results_dir):
    """Repo result folders in a run folder (hidden folders and loose files are not repos)."""
    d = Path(results_dir)
    return sorted(x.name for x in d.iterdir() if x.is_dir() and not x.name.startswith(".")) if d.exists() else []


def relativize(findings, repos_root):
    """Repo findings with an absolute path inside their repo (Semgrep, OSV) get a repo-relative path, so file
    names and fingerprints do not depend on where the workspace sits on disk."""
    for f in findings:
        path = f.get("file") or ""
        if not os.path.isabs(path) or f.get("repo") in report_locate.HOST_REPO_LABELS:
            continue
        root = os.path.realpath(os.path.join(repos_root, f["repo"]))
        real = os.path.realpath(path)
        if real.startswith(root + os.sep):
            f["file"] = os.path.relpath(real, root).replace(os.sep, "/")


def scanner_coverage(results_dir, repos, profile="standard"):
    """{repo label: {scanner: mode}} for every scanner whose raw output exists — what actually ran per repo."""
    cov = {}
    for r in repos:
        d = Path(results_dir) / r
        ran = sorted({name for fname, name in report_model.RAW_FILES.items() if (d / fname).is_file()})
        modes = report_model.scanner_modes(ran, profile)
        if "osv" in modes:  # lockfile scan and SBOM fallback both report as "osv" but cover different inputs
            modes["osv"] = "+".join(m for m, f in (("lockfile", "osv.json"), ("sbom", "osv-sbom.json"))
                                    if (d / f).is_file())
        cov[HOST_LABEL if r == HOST_RESULTS else r] = modes
    return cov


def main():
    ap = argparse.ArgumentParser(description="Generate the security reports for one scan run")
    ap.add_argument("--results-dir", required=True,   help="Directory containing scanner outputs ({repo}/...)")
    ap.add_argument("--config",      required=True,   help="Path to repository.md config file")
    ap.add_argument("--out-dir",     default=None,    help="Write security-report.{md,json,html} here")
    ap.add_argument("--output",      default=None,    help="HTML-only output file (legacy)")
    ap.add_argument("--workspace",   default=".",     help="Workspace root for file links")
    ap.add_argument("--repos-root",  default=None,    help="Folder holding the scanned repos (default: --workspace)")
    ap.add_argument("--home",        default=None,    help="Home folder for host-mode (~/...) paths (default: $HOME)")
    ap.add_argument("--profile",     default="standard", choices=report_model.PROFILES, help="Scan profile")
    ap.add_argument("--since",       default=None,    help="Git ref the run was scoped to (partial run)")
    ap.add_argument("--changed-files", default=None,
                    help="JSON file {repo: [changed paths]} from run-scan.sh --since; findings elsewhere are dropped")
    ap.add_argument("--partial",     action="store_true", help="Scope was limited (--scanner/--repo): no 'fixed' list")
    ap.add_argument("--previous",    default="auto",
                    help="Earlier run folder to compare with: auto (newest older security-run-* beside --out-dir), "
                         "a folder, or none")
    args = ap.parse_args()
    if not args.out_dir and not args.output:
        args.output = "security-report.html"

    config    = parse_config(args.config)
    team      = config.get("team", "unknown")
    org       = config.get("org", "unknown")
    workspace = os.path.abspath(args.workspace)
    repos_root = os.path.abspath(args.repos_root or args.workspace)
    home       = os.path.abspath(args.home or str(Path.home()))

    repos = discover_repos(args.results_dir)
    print(f"\n  Generating reports for team [{team}] / org [{org}]")
    print(f"  Repos found in results: {repos}")

    findings = collect_findings(args.results_dir, repos, workspace)
    report_locate.apply(findings, repos_root, home)
    relativize(findings, repos_root)
    if args.changed_files:
        findings = report_scope.filter_changed(findings, report_scope.load_changed(args.changed_files))
    located = sum(1 for f in findings if f.get("line"))
    print(f"  Total findings parsed: {len(findings)} ({located} located to a line)")

    out_dir = Path(args.out_dir) if args.out_dir else Path(args.output).resolve().parent
    previous, previous_dir = None, None
    if args.previous == "auto":
        previous, previous_dir = report_model.find_previous(out_dir)
    elif args.previous != "none":
        previous_dir = Path(args.previous).resolve()
        previous = report_model.load_report(previous_dir / "security-report.json")
        if previous is None:
            sys.stderr.write("  warning: %s has no valid v2 report; comparing with nothing\n" % previous_dir)
            previous_dir = None
    if previous is not None:
        previous = dict(previous, run_dir=str(previous_dir))
        print(f"  Comparing with previous run: {previous_dir}")

    coverage = scanner_coverage(args.results_dir, repos, args.profile)
    meta = {
        "team": team, "org": org, "config": os.path.abspath(args.config),
        "run_dir": str(out_dir.resolve()),
        "scanners": sorted({f["scanner"] for f in findings} | {s for v in coverage.values() for s in v}),
        "repos": [HOST_LABEL if r == HOST_RESULTS else r for r in repos],
        "skipped": [],
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "profile": args.profile, "since": args.since, "partial": args.partial,
        "coverage": coverage,
        "shai_hulud": report_shaihulud.build(args.results_dir, repos),
        "code_audit": report_audit.build(out_dir),
    }
    same_run = report_model.load_report(out_dir / "security-report.json")
    doc = report_model.build_document(findings, meta, previous=previous, same_run=same_run)
    doc["run"].update(workspace=workspace, repos_root=repos_root, home=home)

    outputs, errors = [], []
    if args.out_dir:
        outputs, errors = write_reports(doc, config, out_dir, args.results_dir)
    if args.output:
        outputs.append(Path(build_html(doc, config, args.results_dir, args.output, org, repos_root)))

    c = doc["counts"]
    v = doc["verification"]
    print(f"\n  Summary: CRITICAL={c['CRITICAL']} HIGH={c['HIGH']} MEDIUM={c['MEDIUM']} LOW={c['LOW']}")
    print(f"  Verification: {v['queued']} queued for review ({v['pending']} pending) — profile {args.profile}")
    for o in outputs:
        print(f"  Report:  {o}")
    return 1 if errors else 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # surface any failure to run-scan.sh, never a silent empty report
        sys.stderr.write("generate-report: failed: %s: %s\n" % (type(exc).__name__, exc))
        sys.exit(1)
