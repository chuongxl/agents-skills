#!/usr/bin/env python3
"""advisory-watch.py - the scheduled job: fetch advisories, match, open an issue per new hit.

Usage:
  python3 -I scripts/advisory-watch.py --github-repo OWNER/NAME --cache DIR
        (--target DIR | --sbom FILE | --inventory FILE) [--env K=V ...]
        [--dry-run] [--no-fetch] [--max-issues N] [--label NAME]

Steps: fetch-advisories.py into --cache, match.py against the target, then for every actionable
finding (and every new vendor bulletin lead) that has no issue yet, create one issue. An issue is
"known" when any issue (open or closed) with the label carries its marker, so a closed issue is
never re-opened and re-runs do not duplicate. Needs GITHUB_TOKEN (issues: write) unless --dry-run.

Exit codes: 0 done, 2 usage/IO/API error. Stdlib only; Python 3.8+. Run with -I.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
API = "https://api.github.com"
ACTIONABLE = ("affected", "affected-end-of-life", "affected-if-condition-holds", "possibly-affected")
MARK_RE = re.compile(r"<!-- jss-advisory:(.+?) -->")


def api(method, path, token, body=None):
    req = urllib.request.Request(API + path, method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28",
                                          "Authorization": "Bearer " + token, "User-Agent": "job-security-scan-watch"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8") or "null")
    except urllib.error.HTTPError as exc:
        raise RuntimeError("GitHub API %s %s -> HTTP %d: %s" % (method, path, exc.code, exc.read()[:200].decode("utf-8", "replace")))
    except urllib.error.URLError as exc:
        raise RuntimeError("GitHub API unreachable: %s" % exc.reason)


def known_markers(repo, label, token):
    marks, page = set(), 1
    while page <= 10:
        items = api("GET", "/repos/%s/issues?labels=%s&state=all&per_page=100&page=%d" % (repo, label, page), token)
        for it in items:
            if "pull_request" in it:
                continue
            marks.update(MARK_RE.findall(it.get("body") or ""))
        if len(items) < 100:
            break
        page += 1
    return marks


def finding_issue(f, target):
    marker = "%s|%s" % (f["id"], f["component"])
    fix = ("Fixed in **%s** (release line %s)." % (f["fixed_in"], f["line"])) if f.get("fixed_in") else "No fixed version known for this line."
    lines = [
        "A new advisory applies to **%s %s**%s." % (f["component"], f["installed"], (" (%s)" % f["location"]) if f.get("location") else ""),
        "", "| | |", "|---|---|",
        "| Advisory | %s%s |" % (f["id"], (" (" + ", ".join(f["aliases"]) + ")") if f["aliases"] else ""),
        "| Severity | %s%s |" % (f["severity"], " - raised: actively exploited (CISA KEV)" if f["exploited"] else ""),
        "| State | %s |" % f["state"],
        "| Source | %s (%s) - %s |" % (f["source"]["vendor"], f["source"]["tier"], f["source"]["url"]),
        "", fix]
    if f.get("unmet_conditions"):
        lines += ["", "Applies only if: " + ", ".join("%s = %s" % (c["type"], c["value"]) for c in f["unmet_conditions"]) + ". Confirm for your deployment."]
    if f.get("conflicts"):
        lines += ["", "Sources disagree on the fixed version: " + "; ".join(
            "%s says %s, %s says %s" % (c["winner"], c["winner_fixed"], c["other"], c["other_fixed"]) for c in f["conflicts"]) + " (vendor value shown above)."]
    lines += ["", "Target: `%s`" % target, "", "<!-- jss-advisory:%s -->" % marker]
    return marker, "[security-advisory] %s affects %s %s (%s)" % (f["id"], f["component"], f["installed"], f["severity"]), "\n".join(lines)


def lead_issue(lead):
    marker = "lead|" + (lead["link"] or lead["title"])
    body = ["A vendor published a security bulletin that is not in the advisory data yet.", "",
            "- Source: `%s`" % lead["source"], "- Title: %s" % lead["title"], "- Link: %s" % (lead["link"] or "(none)"),
            "- CVEs mentioned: %s" % (", ".join(lead["cves"]) or "none"), "",
            "Ingest it so the matcher can use it:", "",
            "    python3 -I scripts/fetch-advisories.py --advisory %s --out assets/advisories/<name>.json" % (lead["link"] or "<url>"),
            "", "Fill in the advisory from the page text and set `source.approved_by` after review.", "",
            "<!-- jss-advisory:%s -->" % marker]
    return marker, "[security-advisory] New %s bulletin: %s" % (lead["source"], lead["title"][:80]), "\n".join(body)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Scheduled advisory watch")
    ap.add_argument("--github-repo", required=True, help="OWNER/NAME where issues are opened")
    ap.add_argument("--cache", required=True)
    ap.add_argument("--target", help="repository directory to inventory")
    ap.add_argument("--sbom")
    ap.add_argument("--inventory")
    ap.add_argument("--env", action="append", default=[])
    ap.add_argument("--no-fetch", action="store_true")
    ap.add_argument("--dry-run", action="store_true", help="print what would be opened; no GitHub access")
    ap.add_argument("--max-issues", type=int, default=10)
    ap.add_argument("--label", default="security-advisory")
    args = ap.parse_args(argv)
    if not (args.target or args.sbom or args.inventory):
        ap.error("give --target, --sbom or --inventory")
    if not re.fullmatch(r"[\w.-]+/[\w.-]+", args.github_repo):
        ap.error("--github-repo must look like OWNER/NAME")
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not args.dry_run and not token:
        print("ERROR: GITHUB_TOKEN is required (or use --dry-run)", file=sys.stderr)
        return 2

    py = [sys.executable, "-I"]
    if not args.no_fetch:
        fetch_cmd = py + [os.path.join(SKILL_DIR, "scripts", "fetch-advisories.py"), "--out", args.cache]
        if args.sbom or args.inventory:
            fetch_cmd += ["--inventory", args.sbom or args.inventory]
        r = subprocess.run(fetch_cmd, capture_output=True, text=True)
        if r.returncode not in (0, 3):     # 3 = some sources unreachable: carry on with what we have
            print("ERROR: fetch failed (exit %d)\n%s" % (r.returncode, r.stdout[-1500:] + r.stderr[-500:]), file=sys.stderr)
            return 2
        print("fetch: exit %d%s" % (r.returncode, " (some sources unreachable)" if r.returncode == 3 else ""))

    report_path = os.path.join(args.cache, "match-report.json")
    cmd = py + [os.path.join(SKILL_DIR, "scripts", "match.py"), "--cache", args.cache, "--output", report_path, "--fail-on", "none", "--format", "json", "--allow-empty"]
    for flag, val in (("--repo", args.target), ("--sbom", args.sbom), ("--inventory", args.inventory)):
        if val:
            cmd += [flag, val]
    for e in args.env:
        cmd += ["--env", e]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print("ERROR: match failed\n%s" % r.stderr[-1500:], file=sys.stderr)
        return 2
    report = json.loads(r.stdout)
    target = args.target or args.sbom or args.inventory

    candidates = [finding_issue(f, target) for f in report["findings"] if f["state"] in ACTIONABLE]
    leads_path = os.path.join(args.cache, "enrichment", "leads.json")
    if os.path.exists(leads_path):
        with open(leads_path, encoding="utf-8") as fh:
            candidates += [lead_issue(l) for l in json.load(fh).get("leads", []) if l.get("cves")]

    known = set() if args.dry_run and not token else known_markers(args.github_repo, args.label, token)
    new = [c for c in candidates if c[0] not in known]
    print("%d applicable item(s), %d already tracked, %d new" % (len(candidates), len(candidates) - len(new), len(new)))
    created = 0
    for marker, title, body in new[:args.max_issues]:
        if args.dry_run:
            print("[dry-run] would open: %s" % title)
        else:
            res = api("POST", "/repos/%s/issues" % args.github_repo, token, {"title": title, "body": body, "labels": [args.label]})
            print("opened #%s: %s" % (res["number"], title))
        created += 1
    if len(new) > args.max_issues:
        print("%d more item(s) not opened (--max-issues %d)" % (len(new) - args.max_issues, args.max_issues))
    return 0


if __name__ == "__main__":
    sys.exit(main())
