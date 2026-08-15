#!/usr/bin/env python3
"""
generate-report.py — Generate a self-contained HTML security report.

Usage:
  python3 generate-report.py --results-dir DIR --config repository.md [--output report.html] [--workspace PATH]

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
            "type": "sast",
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
            for vuln in pkg.get("vulnerabilities", []):
                sev = "MEDIUM"
                for severity in vuln.get("severity", []):
                    if severity.get("type") == "CVSS_V3":
                        score = float(severity.get("score", "0").split("/")[0] if "/" in severity.get("score","") else "0")
                        if score >= 9.0:   sev = "CRITICAL"
                        elif score >= 7.0: sev = "HIGH"
                        elif score >= 4.0: sev = "MEDIUM"
                        else:              sev = "LOW"
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

def collect_findings(results_dir, repos, workspace):
    parsers = [parse_gitleaks, parse_trufflehog, parse_trivy, parse_semgrep, parse_hadolint, parse_osv]
    all_findings = []
    for repo in repos:
        for parser in parsers:
            all_findings.extend(parser(repo, results_dir, workspace))
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


def build_html(findings, config, results_dir, output_path, org):
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

            # CVE/Rule ID cell
            id_html = cve_link(f["rule_id"], f["url"]) or '<span style="color:var(--text3)">—</span>'

            # Description (truncated)
            desc = html.escape(f["description"][:200]) if f["description"] else ""
            title_txt = html.escape(f["title"][:100]) if f["title"] else ""

            rows_html += f"""
        <tr data-sev="{sev}" data-repo="{html.escape(repo)}" data-scan="{html.escape(scan)}" data-type="{html.escape(ftype)}">
          <td class="sev-col"><span class="badge {sev}">{sev}</span></td>
          <td class="repo-col"><code style="font-size:12px">{html.escape(repo)}</code></td>
          <td class="scanner-col"><span class="chip {html.escape(scan)}">{html.escape(scan)}</span></td>
          <td class="file-col">{file_html}</td>
          <td class="pkg-col">{pkg_html}</td>
          <td class="id-col">{id_html}</td>
          <td class="desc-col"><strong style="color:var(--text)">{title_txt}</strong><br><small>{desc}</small></td>
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
           .replace("{{ROWS}}",        rows_html))

    Path(output_path).write_text(doc, encoding="utf-8")
    print(f"  📄 HTML report → {output_path}")
    return output_path


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="Generate HTML security report")
    ap.add_argument("--results-dir", required=True,   help="Directory containing scanner JSON outputs")
    ap.add_argument("--config",      required=True,   help="Path to repository.md config file")
    ap.add_argument("--output",      default="security-report.html", help="Output HTML file path")
    ap.add_argument("--workspace",   default=".",     help="Monorepo workspace root for file links")
    args = ap.parse_args()

    config    = parse_config(args.config)
    team      = config.get("team", "unknown")
    org       = config.get("org", "unknown")
    workspace = os.path.abspath(args.workspace)

    # Discover repos from results dir
    results_dir = Path(args.results_dir)
    repos = sorted([d.name for d in results_dir.iterdir() if d.is_dir()]) if results_dir.exists() else []

    print(f"\n  Generating HTML report for team [{team}] / org [{org}]")
    print(f"  Repos found in results: {repos}")

    findings = collect_findings(args.results_dir, repos, workspace)
    print(f"  Total findings parsed: {len(findings)}")

    output_path = build_html(findings, config, args.results_dir, args.output, org)

    # Summary to stdout
    counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for f in findings:
        sev = f["severity"].upper()
        if sev in counts:
            counts[sev] += 1

    print(f"\n  Summary: CRITICAL={counts['CRITICAL']} HIGH={counts['HIGH']} MEDIUM={counts['MEDIUM']} LOW={counts['LOW']}")
    print(f"  Open:    open {output_path}\n")


if __name__ == "__main__":
    main()
