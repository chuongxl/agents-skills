"""Stable finding fingerprints, run-to-run diff and the accepted-findings baseline.

Fingerprints identify one root issue across runs: scanner + repo + rule + file + package (+ the code line for
code findings), never the line number or a version, so moving code or bumping a still-vulnerable version keeps
the same fingerprint. Repeats inside one run get a -2, -3 ... suffix in line order.

The diff compares each (repo, scanner) pair with the most recent earlier run in which that pair actually ran,
so a narrow run (`--scanner trivy`) never makes other scanners' findings look fixed or new.
Stdlib only; Python 3.8+.
"""
import hashlib
import json
import os
import re
from datetime import date

RAW_OUTPUT = {  # scanner name in findings -> raw file that proves the scanner ran for a repo
    "gitleaks": "gitleaks.json",
    "trivy": "trivy.json",
    "semgrep": "semgrep.json",
    "hadolint": "hadolint.txt",
    "osv": "osv.json",
    "advisory": "advisories.json",
    "trufflehog": "trufflehog.json",
    "shai-hulud": "shai-hulud.json",
    "audit": os.path.join("audit", "findings.json"),
}
HOST_DIR, HOST_LABEL = "_host", "this machine"
MAX_HISTORY_RUNS = 30
RUN_NAME = re.compile(r"^security-run-\d{8}-\d{6}(-\d+)?$")
_WS = re.compile(r"\s+")


def _norm(value):
    return _WS.sub(" ", str(value or "")).strip()


def base_fingerprint(f):
    if f.get("scanner") == "audit" and f.get("rule_id"):
        return "audit:" + f["rule_id"]
    parts = [f.get("repo"), f.get("scanner"), f.get("rule_id") or _norm(f.get("title")), f.get("file"),
             f.get("package")]
    if f.get("type") != "secret" and not f.get("package") and f.get("code"):
        parts.append(_norm(f["code"]))
    digest = hashlib.sha256("\x1f".join(_norm(p) for p in parts).encode("utf-8")).hexdigest()[:16]
    return "%s:%s" % (f.get("scanner") or "finding", digest)


def assign_fingerprints(findings):
    """Set f['fingerprint'] on every finding (in place); repeats get -2, -3 ... in line order."""
    groups = {}
    for f in findings:
        groups.setdefault(base_fingerprint(f), []).append(f)
    for base, group in groups.items():
        group.sort(key=lambda f: (f.get("line") or 0, _norm(f.get("code")), _norm(f.get("title"))))
        for i, f in enumerate(group):
            f["fingerprint"] = base if i == 0 else "%s-%d" % (base, i + 1)
    return findings


def scanners_ran(run_dir):
    """{(repo label, scanner)} that produced raw output in a run folder."""
    pairs = set()
    try:
        repos = [d for d in os.listdir(run_dir) if os.path.isdir(os.path.join(run_dir, d)) and not d.startswith(".")]
    except OSError:
        return pairs
    for repo in repos:
        label = HOST_LABEL if repo == HOST_DIR else repo
        for scanner, raw in RAW_OUTPUT.items():
            if os.path.isfile(os.path.join(run_dir, repo, raw)):
                pairs.add((label, scanner))
    return pairs


def earlier_runs(run_dir):
    """Earlier run folders next to run_dir, newest first (by folder name, which sorts by time)."""
    run_dir = os.path.abspath(run_dir)
    root, name = os.path.dirname(run_dir), os.path.basename(run_dir)
    try:
        names = [n for n in os.listdir(root) if RUN_NAME.match(n) and n < name
                 and os.path.isfile(os.path.join(root, n, "security-report.json"))]
    except OSError:
        return []
    return [os.path.join(root, n) for n in sorted(names, reverse=True)[:MAX_HISTORY_RUNS]]


def _load_report(path):
    try:
        with open(os.path.join(path, "security-report.json"), encoding="utf-8") as fh:
            doc = json.load(fh)
        return doc if isinstance(doc, dict) and isinstance(doc.get("findings"), list) else None
    except (OSError, ValueError):
        return None


def _prior_findings(doc):
    findings = [dict(f) for f in doc["findings"] if isinstance(f, dict)]
    if not all(f.get("fingerprint") for f in findings):  # schema v1 reports: derive them the same way
        for f in findings:
            f.pop("fingerprint", None)
        assign_fingerprints(findings)
    for f in doc.get("baseline", {}).get("accepted", []) if isinstance(doc.get("baseline"), dict) else []:
        if isinstance(f, dict) and f.get("fingerprint"):
            findings.append(dict(f))
    return findings


def diff(findings, run_dir, current_pairs, previous=None):
    """Mark f['diff_status'] new|open and f['first_seen']; return the diff summary for the report."""
    runs = [previous] if previous else earlier_runs(run_dir)
    state = {}  # (repo, scanner) -> (run path, generated_at, {fingerprint: finding})
    for run in runs:
        doc = _load_report(run)
        if not doc:
            continue
        pairs = scanners_ran(run)
        by_pair = {}
        for f in _prior_findings(doc):
            by_pair.setdefault((f.get("repo"), f.get("scanner")), {})[f["fingerprint"]] = f
        for pair in pairs | set(by_pair):
            if pair not in state:
                state[pair] = (run, doc.get("generated_at") or "", by_pair.get(pair, {}))
    for f in findings:
        prior = state.get((f.get("repo"), f.get("scanner")))
        old = prior[2].get(f["fingerprint"]) if prior else None
        if old is not None:
            f["diff_status"] = "open"
            f["first_seen"] = old.get("first_seen") or prior[1] or None
        else:
            f["diff_status"] = "new" if prior else "first-scan"
            f["first_seen"] = None
    current = set(f["fingerprint"] for f in findings)
    fixed, not_rechecked = [], 0
    for pair, (run, generated_at, prior) in sorted(state.items(), key=lambda kv: (str(kv[0][0]), str(kv[0][1]))):
        for fp, old in sorted(prior.items()):
            if fp in current:
                continue
            if pair in current_pairs:
                fixed.append({"fingerprint": fp, "repo": old.get("repo"), "scanner": old.get("scanner"),
                              "severity": old.get("severity"), "title": old.get("title"), "file": old.get("file"),
                              "line": old.get("line"), "rule_id": old.get("rule_id"),
                              "last_seen": generated_at, "last_run": os.path.basename(run)})
            else:
                not_rechecked += 1
    return {
        "compared_runs": sorted(set(os.path.basename(v[0]) for v in state.values()), reverse=True),
        "new": sum(1 for f in findings if f["diff_status"] == "new"),
        "open": sum(1 for f in findings if f["diff_status"] == "open"),
        "first_scan": sum(1 for f in findings if f["diff_status"] == "first-scan"),
        "fixed": len(fixed),
        "not_rechecked": not_rechecked,
        "fixed_findings": fixed,
    }


# ── baseline ──────────────────────────────────────────────────────────────────

def load_baseline(path, today=None):
    """{fingerprint: entry} of active entries, plus expired and invalid entries, from a baseline file.

    {"version": 1, "entries": [{"fingerprint": "...", "reason": "why this is accepted",
                                "expires": "YYYY-MM-DD" (optional), "owner": "..." (optional)}]}
    """
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
        result["invalid"].append({"entry": None, "reason": "baseline must be {\"version\": 1, \"entries\": [...]}"})
        return result
    today = today or date.today()
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("fingerprint"), str) \
                or not _norm(entry.get("reason")):
            result["invalid"].append({"entry": entry, "reason": "each entry needs a fingerprint and a reason"})
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


def apply_baseline(findings, baseline):
    """Split findings into (reported, accepted). Accepted findings carry their baseline entry."""
    reported, accepted, used = [], [], set()
    for f in findings:
        entry = baseline["active"].get(f.get("fingerprint"))
        if entry is None:
            reported.append(f)
            continue
        used.add(f["fingerprint"])
        accepted.append(dict(f, baseline_reason=entry["reason"], baseline_expires=entry.get("expires"),
                             baseline_owner=entry.get("owner")))
    unused = sorted(fp for fp in baseline["active"] if fp not in used)
    return reported, accepted, unused
