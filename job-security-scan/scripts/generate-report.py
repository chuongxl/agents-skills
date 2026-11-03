#!/usr/bin/env python3
"""
generate-report.py — Generate the security reports (Markdown, JSON, HTML) for one scan run.

Usage:
  python3 generate-report.py --results-dir DIR --config repository.md --out-dir DIR
                             [--repos-root PATH] [--home PATH] [--workspace PATH]
                             [--baseline FILE] [--previous RUN_DIR | --no-diff]
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

import audit_report    # noqa: E402
import history         # noqa: E402
import report_formats  # noqa: E402
import report_locate   # noqa: E402


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


def collect_findings(results_dir, repos, workspace):
    parsers = [parse_gitleaks, parse_trufflehog, parse_trivy, parse_semgrep, parse_hadolint, parse_osv,
               parse_advisories, parse_shai_hulud]
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


def build_html(findings, config, results_dir, output_path, org, meta=None):
    team = config.get("team", "unknown")
    scan_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0, "INFO": 0}
    repos   = sorted(set(f["repo"] for f in findings))
    scanners = sorted(set(f["scanner"] for f in findings))
    types   = sorted(set(f["type"] for f in findings))

    for f in findings:
        sev = f["severity"].upper()
        if sev in counts:
            counts[sev] += 1

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

    sev_order_list = [s for s in ["CRITICAL","HIGH","MEDIUM","LOW","INFO"] if s in set(f["severity"] for f in findings)]
    diffs = sorted(set(f.get("diff_status") or "" for f in findings) - {""})

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
      <label>Change</label>
      <select id="f-diff">{options(diffs, "Any")}</select>
      <button class="btn-reset" onclick="resetFilters()">Reset</button>
      <span class="filter-count" id="visible-count">{total} findings</span>
    </div>"""

    # ── Table rows ─────────────────────────────────────────────────────────────
    rows_html = ""
    if not findings:
        rows_html = '<tr><td colspan="7" class="empty"><div class="icon">🟢</div>No findings — all repos are clean!</td></tr>'
    else:
        for f in findings:
            sev   = f["severity"].upper()
            repo  = f["repo"]
            scan  = f["scanner"]
            ftype = f["type"]

            # Package cell
            pkg_parts = []
            if f["package"]:
                pkg_parts.append(f'<div class="pkg-name">{html.escape(f["package"])}</div>')
            if f["installed_version"]:
                pkg_parts.append(f'<div class="pkg-version">installed: {html.escape(f["installed_version"])}</div>')
            if f["fixed_version"]:
                pkg_parts.append(f'<div class="pkg-fix">→ fix: {html.escape(f["fixed_version"])}</div>')
            pkg_html = "\n".join(pkg_parts) or '<span style="color:var(--text3)">—</span>'

            # File link cell
            file_html = file_link(f, org, repo) or '<span style="color:var(--text3)">—</span>'
            if f.get("code"):
                file_html += f'<div class="code-excerpt"><code>{html.escape(f["code"])}</code></div>'

            # CVE/Rule ID cell
            id_html = cve_link(f["rule_id"], f["url"]) or '<span style="color:var(--text3)">—</span>'

            # Description (truncated)
            desc = html.escape(f["description"][:200]) if f["description"] else ""
            title_txt = html.escape(f["title"][:100]) if f["title"] else ""

            diff_status = f.get("diff_status") or ""
            marks = ('<span class="mark new">🆕 new</span> ' if diff_status == "new" else "") + \
                    ('<span class="mark audit">🧠 agent-verified</span> ' if f.get("verdict") == "confirmed" else "")
            details = f.get("details") or {}
            if details:
                desc += ("<br><small><b>Observed:</b> " + html.escape(str(details.get("observed_result", ""))[:300])
                         + "<br><b>Fix (guidance):</b> " + html.escape(str(details.get("remediation", ""))[:300])
                         + "</small>")
            rows_html += f"""
        <tr data-sev="{html.escape(sev)}" data-repo="{html.escape(repo)}" data-scan="{html.escape(scan)}" data-type="{html.escape(ftype)}" data-diff="{html.escape(diff_status)}">
          <td class="sev-col"><span class="badge {html.escape(sev)}">{html.escape(sev)}</span></td>
          <td class="repo-col"><code style="font-size:12px">{html.escape(repo)}</code></td>
          <td class="scanner-col"><span class="chip {html.escape(scan)}">{html.escape(scan)}</span></td>
          <td class="file-col">{file_html}</td>
          <td class="pkg-col">{pkg_html}</td>
          <td class="id-col">{id_html}</td>
          <td class="desc-col">{marks}<strong style="color:var(--text)">{title_txt}</strong><br><small>{desc}</small></td>
        </tr>"""

    # ── Render template ────────────────────────────────────────────────────────
    if not TEMPLATE_PATH.exists():
        raise FileNotFoundError(f"Template not found: {TEMPLATE_PATH}")

    title = f"Security Scan \u2014 {html.escape(team)} / {html.escape(org)}"
    doc = TEMPLATE_PATH.read_text(encoding="utf-8")
    doc = (doc
           .replace("{{TITLE}}",       title)
           .replace("{{TEAM}}",        html.escape(team))
           .replace("{{ORG}}",         html.escape(org))
           .replace("{{SCAN_TIME}}",   scan_time)
           .replace("{{RESULTS_DIR}}", html.escape(str(results_dir)))
           .replace("{{REPO_COUNT}}",  str(len(repos)))
           .replace("{{SCANNERS}}",    html.escape(", ".join(scanners) or "\u2014"))
           .replace("{{TOTAL}}",       str(total))
           .replace("{{CARDS}}",       cards_html)
           .replace("{{FILTERS}}",     filters_html)
           .replace("{{ROWS}}",        rows_html)
           .replace("{{SECTIONS}}",    html_sections(meta or {})))

    Path(output_path).write_text(doc, encoding="utf-8")
    print(f"  📄 HTML report → {output_path}")
    return output_path


def _h(value):
    return html.escape(str(value if value is not None else ""))


def html_sections(meta):
    """Changes since last run, deep-audit coverage and leads, accepted findings."""
    parts = []
    diff = meta.get("diff")
    if diff and diff.get("compared_runs"):
        items = "".join(
            f'<li><s>{_h(f.get("title"))}</s> <small>({_h(f.get("repo"))} · {_h(f.get("severity"))} · '
            f'{_h(f.get("scanner"))} · {_h(f.get("file"))}{":" + _h(f["line"]) if f.get("line") else ""})</small></li>'
            for f in diff.get("fixed_findings", []))
        parts.append(
            f'<section class="panel"><h2>🔁 Changes since last run</h2><p>🆕 new <b>{diff["new"]}</b> · '
            f'⏳ still open <b>{diff["open"]}</b> · ✅ fixed <b>{diff["fixed"]}</b>'
            + (f' · not re-checked <b>{diff["not_rechecked"]}</b>' if diff.get("not_rechecked") else "")
            + f'</p><p><small>Compared with: {_h(", ".join(diff["compared_runs"]))}</small></p>'
            + (f'<h3>✅ Fixed</h3><ul>{items}</ul>' if items else "") + '</section>')
    for repo, a in sorted((meta.get("audits") or {}).items()):
        cov = " · ".join(f"{_h(k)} {v}" for k, v in sorted((a.get("coverage") or {}).items())) or "—"
        rows = "".join(
            f'<tr><td>{_h(n["title"])}</td><td><code>{_h(n.get("file"))}:{_h(n.get("line"))}</code></td>'
            f'<td>{_h(report_formats.first_blocker(n))}</td><td>{_h(report_formats.short_plan(n))}</td></tr>'
            for n in a.get("needs_validation") or [])
        hard = "".join(f"<li>{_h(h)}</li>" for h in (a.get("hardening") or [])[:30])
        gaps = "".join(f'<li>{_h(d["status"])}: {_h(d["surface"])} × {_h(d["attack_class"])} — {_h(d["reason"])}</li>'
                       for d in (a.get("deferred") or [])[:30])
        warn = ""
        if a.get("errors"):
            warn += f'<p class="warn">⚠️ Audit output not merged: {_h("; ".join(a["errors"][:3]))}</p>'
        if a.get("incomplete_reason"):
            warn += f'<p class="warn">⚠️ Incomplete: {_h(a["incomplete_reason"])} — a partial pass</p>'
        parts.append(
            f'<section class="panel"><h2>🧠 Deep audit — {_h(repo)}</h2>'
            f'<p>Profile <b>{_h(a.get("profile") or "—")}</b> · status <b>{_h(a.get("run_status") or "—")}</b> · '
            f'execution <b>{_h(a.get("execution_policy") or "—")}</b></p><p>Coverage: {cov}</p>'
            f'<p>Confirmed <b>{a.get("confirmed", 0)}</b> (in the table, marked 🧠) · needs validation '
            f'<b>{len(a.get("needs_validation") or [])}</b> · rejected <b>{a.get("rejected", 0)}</b></p>{warn}'
            + (f'<h3>Needs validation (no severity)</h3><table class="mini"><tr><th>Lead</th><th>Where</th>'
               f'<th>Blocker</th><th>How to resolve</th></tr>{rows}</table>' if rows else "")
            + (f'<h3>Not covered this run</h3><ul>{gaps}</ul>' if gaps else "")
            + (f'<h3>Hardening notes (not vulnerabilities)</h3><ul>{hard}</ul>' if hard else "")
            + '</section>')
    baseline = meta.get("baseline") or {}
    if baseline.get("accepted") or baseline.get("expired") or baseline.get("unused"):
        items = "".join(
            f'<li>{_h(f.get("title"))} <small>({_h(f.get("repo"))} · {_h(f.get("severity"))} · '
            f'<code>{_h(f.get("fingerprint"))}</code>)</small> — {_h(f.get("baseline_reason"))}</li>'
            for f in baseline.get("accepted", []))
        parts.append(
            f'<section class="panel"><h2>🤝 Accepted findings (baseline)</h2><ul>{items}</ul>'
            + (f'<p><small>Expired: {_h(", ".join(e.get("fingerprint", "") for e in baseline["expired"]))}</small></p>'
               if baseline.get("expired") else "")
            + (f'<p><small>Matched nothing this run: {_h(", ".join(baseline["unused"]))}</small></p>'
               if baseline.get("unused") else "")
            + '</section>')
    return "\n".join(parts)


# ─── Main ─────────────────────────────────────────────────────────────────────

def discover_repos(results_dir):
    """Repo result folders in a run folder (hidden folders and loose files are not repos)."""
    d = Path(results_dir)
    return sorted(x.name for x in d.iterdir() if x.is_dir() and not x.name.startswith(".")) if d.exists() else []


def main():
    ap = argparse.ArgumentParser(description="Generate the security reports for one scan run")
    ap.add_argument("--results-dir", required=True,   help="Directory containing scanner outputs ({repo}/...)")
    ap.add_argument("--config",      required=True,   help="Path to repository.md config file")
    ap.add_argument("--out-dir",     default=None,    help="Write security-report.{md,json,html} here")
    ap.add_argument("--output",      default=None,    help="HTML-only output file (legacy)")
    ap.add_argument("--workspace",   default=".",     help="Workspace root for file links")
    ap.add_argument("--repos-root",  default=None,    help="Folder holding the scanned repos (default: --workspace)")
    ap.add_argument("--home",        default=None,    help="Home folder for host-mode (~/...) paths (default: $HOME)")
    ap.add_argument("--baseline",    default=None,    help="Accepted-findings file (fingerprint + reason)")
    ap.add_argument("--previous",    default=None,    help="Compare with this run folder only (default: earlier runs)")
    ap.add_argument("--no-diff",     action="store_true", help="Do not compare with earlier runs")
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
    audits = {}
    for repo in repos:
        try:
            merged, summary = audit_report.load(args.results_dir, repo, workspace)
        except Exception as exc:  # a broken audit folder must not cost the scanner report
            merged, summary = [], {"valid": False, "errors": ["%s: %s" % (type(exc).__name__, exc)]}
        if summary is not None:
            audits[repo] = summary
            findings.extend(merged)
    findings.sort(key=lambda f: (severity_order(f["severity"]), f["repo"], f["scanner"]))
    report_locate.apply(findings, repos_root, home)
    located = sum(1 for f in findings if f.get("line"))
    print(f"  Total findings parsed: {len(findings)} ({located} located to a line)")

    history.assign_fingerprints(findings)
    current_pairs = history.scanners_ran(args.results_dir)
    if args.no_diff:
        diff = None
    else:
        diff = history.diff(findings, args.results_dir, current_pairs, previous=args.previous)
        print(f"  Since earlier runs: {diff['new']} new, {diff['open']} still open, {diff['fixed']} fixed")
    baseline = history.load_baseline(args.baseline)
    findings, accepted, unused = history.apply_baseline(findings, baseline)
    if args.baseline:
        print(f"  Baseline: {len(accepted)} accepted finding(s) hidden from the counts")
    run_meta = {}
    try:
        run_meta = json.loads((Path(args.results_dir) / "run-metadata.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pass

    outputs = []
    if args.out_dir:
        out_dir = Path(args.out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        meta = {
            "team": team, "org": org, "config": os.path.abspath(args.config),
            "run_dir": str(out_dir.resolve()),
            "scanners": sorted({f["scanner"] for f in findings} | {sc for _, sc in current_pairs}),
            "repos": [HOST_LABEL if r == HOST_RESULTS else r for r in repos],
            "skipped": [],
            "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "diff": diff,
            "baseline": {"path": os.path.abspath(args.baseline) if args.baseline else None,
                         "accepted": accepted, "unused": unused, "expired": baseline["expired"],
                         "invalid": baseline["invalid"]},
            "audits": dict((HOST_LABEL if r == HOST_RESULTS else r, a) for r, a in audits.items()),
            "source_refs": run_meta.get("source_refs", {}),
            "run_options": dict((k, run_meta.get(k)) for k in ("scanner", "profile", "since", "budget")
                                if run_meta.get(k) not in (None, "")),
        }
        (out_dir / "security-report.json").write_text(
            json.dumps(report_formats.build_json(findings, meta), indent=2) + "\n", encoding="utf-8")
        (out_dir / "security-report.md").write_text(report_formats.build_markdown(findings, meta), encoding="utf-8")
        outputs += [out_dir / "security-report.md", out_dir / "security-report.json"]
        outputs.append(Path(build_html(findings, config, args.results_dir, str(out_dir / "security-report.html"), org,
                                       meta)))
    if args.output:
        outputs.append(Path(build_html(findings, config, args.results_dir, args.output, org)))

    counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for f in findings:
        sev = f["severity"].upper()
        if sev in counts:
            counts[sev] += 1
    print(f"\n  Summary: CRITICAL={counts['CRITICAL']} HIGH={counts['HIGH']} MEDIUM={counts['MEDIUM']} LOW={counts['LOW']}")
    for o in outputs:
        print(f"  Report:  {o}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # surface any failure to run-scan.sh, never a silent empty report
        sys.stderr.write("generate-report: failed: %s: %s\n" % (type(exc).__name__, exc))
        sys.exit(1)
