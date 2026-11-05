"""The v2 security-report model: stable fingerprints, verdicts, changes since the previous run.

A fingerprint identifies a finding across runs without depending on its line number, so moved code keeps its
identity while edited code gets a new one (and is verified again). Secrets are fingerprinted by location only —
their code line is never hashed or stored.

Verdicts follow the contract adapted from Cloudflare's security-audit skill (MIT, see
references/third-party/cloudflare-security-audit-LICENSE): confirmed / needs_validation / rejected.
Stdlib only; Python 3.8+.
"""

import hashlib
import re

SCHEMA_VERSION = 2
SEVERITIES = ("CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO")
IMPACTS = ("critical", "high", "medium", "low", "informational")
LIKELIHOODS = ("high", "medium", "low")
VERDICTS = ("confirmed", "needs_validation", "rejected")
CHANGES = ("new", "unchanged")
PROFILES = ("quick", "standard", "deep")
QUEUE_SEVERITIES = {"quick": (), "standard": ("CRITICAL", "HIGH"), "deep": ("CRITICAL", "HIGH", "MEDIUM")}
DEPENDENCY_TYPES = ("vulnerability", "supply-chain")
FINDING_KEYS = ("repo", "scanner", "type", "severity", "file", "line", "code", "package", "installed_version",
                "fixed_version", "rule_id", "title", "description", "url")
VERDICT_KEYS = ("fingerprint", "change", "verdict", "verified_severity", "verdict_detail", "carried")

# raw output file -> scanner name, used to know which scanners actually ran for a repo
RAW_FILES = {"gitleaks.json": "gitleaks", "trivy.json": "trivy", "semgrep.json": "semgrep",
             "hadolint.txt": "hadolint", "osv.json": "osv", "osv-sbom.json": "osv", "advisories.json": "advisory",
             "trufflehog.json": "trufflehog", "shai-hulud.json": "shai-hulud"}
# the deep audit is a scanner only when its results validated (see audit_report.load); its coverage mode is
# "audit:<profile>" so a quick audit never marks findings of a deep audit as fixed
AUDIT_SCANNER = "audit"


def _norm_code(code):
    return re.sub(r"\s+", "", str(code or ""))


def fingerprint(f):
    """16 hex chars of SHA-256 over a line-independent key (see module docstring)."""
    kind = f.get("type")
    if kind == "secret":
        parts = (f.get("scanner"), f.get("rule_id"), f.get("repo"), f.get("file"), str(f.get("line") or ""))
    elif f.get("package") and (kind in DEPENDENCY_TYPES or f.get("installed_version")):
        parts = (f.get("scanner"), f.get("rule_id"), f.get("repo"), f.get("file"), f.get("package"),
                 f.get("installed_version"))
    else:
        anchor = _norm_code(f.get("code")) or str(f.get("line") or "")
        parts = (f.get("scanner"), f.get("rule_id"), f.get("repo"), f.get("file"), anchor)
    key = "\x1f".join(str(p or "") for p in parts)
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]


def _number_occurrences(rows):
    """Distinct findings that share a key (the same package@version twice in one lockfile, the same line of
    code twice in one file) get the base fingerprint for the first occurrence by line and a numbered one for
    the rest, so fingerprints stay unique and stable while the occurrences keep their order."""
    groups = {}
    for r in rows:
        groups.setdefault(r["fingerprint"], []).append(r)
    for base, group in groups.items():
        if len(group) < 2:
            continue
        group.sort(key=lambda r: (r.get("line") or 0, str(r.get("code") or "")))
        for n, r in enumerate(group[1:], 1):
            r["fingerprint"] = hashlib.sha256(("%s#%d" % (base, n)).encode("ascii")).hexdigest()[:16]


def effective_severity(f):
    if f.get("verdict") == "confirmed" and f.get("verified_severity"):
        return f["verified_severity"]
    return (f.get("severity") or "").upper()


def counts_of(findings):
    counts = dict((s, 0) for s in SEVERITIES)
    for f in findings:
        if f.get("verdict") == "rejected":
            continue
        sev = effective_severity(f)
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
        counts = counts_of(mine)
        out.append({"name": name, "status": _status(counts), "counts": counts,
                    "secrets": sum(1 for f in mine if f.get("type") == "secret" and f.get("verdict") != "rejected")})
    return out


def is_queued(f, profile):
    """Does this profile ask for independent verification of this finding?"""
    return (f.get("severity") or "").upper() in QUEUE_SEVERITIES.get(profile or "standard", ())


def verification_summary(findings, profile):
    queued = [f for f in findings if is_queued(f, profile)]
    out = {"profile": profile, "queued": len(queued), "pending": sum(1 for f in queued if not f.get("verdict"))}
    for v in VERDICTS:
        out[v] = sum(1 for f in findings if f.get("verdict") == v)
    return out


def _modes(cov):
    """Coverage of one repo as {scanner: mode}; a plain list means every listed scanner ran in 'full' mode."""
    if isinstance(cov, dict):
        return dict((str(k), str(v)) for k, v in cov.items())
    return dict((str(s), "full") for s in (cov or []))


def scanner_modes(scanners, profile):
    """How each scanner ran under a profile; only equal modes in both runs can mark a finding fixed."""
    out = {}
    for s in scanners:
        if s == "gitleaks":
            out[s] = "worktree" if profile == "quick" else "history"
        elif s == "trivy":
            out[s] = "low" if profile == "deep" else "medium"
        elif s == AUDIT_SCANNER:
            out[s] = "audit:%s" % profile
        else:
            out[s] = "full"
    return out


def _compare(findings, coverage, previous, partial):
    """Set change/carry on findings; return (fixed list, previous run dir or None)."""
    prev_rows = {}
    prev_cov = {}
    if previous and previous.get("schema_version", 0) >= 2:
        before = list(previous.get("findings", [])) + list((previous.get("baseline") or {}).get("accepted", []))
        prev_rows = dict((p["fingerprint"], p) for p in before if p.get("fingerprint"))
        prev_cov = (previous.get("run") or {}).get("coverage") or {}
    for f in findings:
        p = prev_rows.get(f["fingerprint"])
        f["change"] = "unchanged" if p else "new"
        if p and p.get("verdict") and not f.get("verdict"):
            f["verdict"] = p["verdict"]
            f["verified_severity"] = p.get("verified_severity")
            f["verdict_detail"] = p.get("verdict_detail") or {}
            f["carried"] = True
    if not prev_rows or partial or (previous.get("run") or {}).get("partial"):
        return [], (previous or {}).get("run_dir") if prev_rows else None
    seen = set(f["fingerprint"] for f in findings)
    fixed = []
    for fp, p in sorted(prev_rows.items()):
        now, before = _modes(coverage.get(p.get("repo"))), _modes(prev_cov.get(p.get("repo")))
        scanner = p.get("scanner")
        same = scanner in now and now.get(scanner) == before.get(scanner)
        if fp not in seen and same and p.get("verdict") != "rejected":
            fixed.append(dict((k, p.get(k)) for k in ("fingerprint", "repo", "scanner", "rule_id", "file",
                                                      "package", "title", "severity")))
    return fixed, previous.get("run_dir")


def build_document(findings, meta, previous=None):
    """v2 report document. `meta`: team, org, config, run_dir, scanners, repos, skipped, generated_at,
    profile, since, coverage ({repo: [scanners that ran]}). `previous`: the prior run's document or None."""
    profile = meta.get("profile") or "standard"
    rows, seen_rows = [], set()
    for f in findings:
        row = dict((k, f.get(k)) for k in FINDING_KEYS)
        if row.get("type") == "secret":
            row["code"] = ""
        exact = tuple(str(row.get(k)) for k in FINDING_KEYS)
        if exact in seen_rows:          # a scanner repeated the same row verbatim
            continue
        seen_rows.add(exact)
        row["fingerprint"] = f.get("fingerprint") or fingerprint(row)
        row["verdict"] = f.get("verdict")
        row["verified_severity"] = f.get("verified_severity")
        row["verdict_detail"] = f.get("verdict_detail") or {}
        row["carried"] = bool(f.get("carried"))
        rows.append(row)
    _number_occurrences(rows)
    partial = bool(meta.get("since")) or bool(meta.get("partial"))
    fixed, prev_dir = _compare(rows, meta.get("coverage") or {}, previous, partial)
    baseline = None
    if meta.get("baseline"):    # accepted findings leave the counts but stay visible (baseline.py)
        import baseline as baseline_mod
        rows, accepted, unused = baseline_mod.split(rows, meta["baseline"])
        baseline = baseline_mod.section(meta["baseline"], accepted, unused)
    doc = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": meta.get("generated_at", ""),
        "team": meta.get("team", ""),
        "org": meta.get("org", ""),
        "config": meta.get("config", ""),
        "run_dir": meta.get("run_dir", ""),
        "run": {"profile": profile, "since": meta.get("since"), "partial": partial,
                "previous_run": prev_dir, "coverage": meta.get("coverage") or {}},
        "scanners": list(meta.get("scanners", [])),
        "counts": counts_of(rows),
        "repos": repo_summaries(rows, meta.get("repos", [])),
        "skipped": list(meta.get("skipped", [])),
        "fixed": fixed,
        "shai_hulud": meta.get("shai_hulud") or {"ran": False, "ioc_version": None, "targets": []},
        "verification": verification_summary(rows, profile),
        "findings": rows,
    }
    if baseline:
        doc["baseline"] = baseline
    if meta.get("audit"):
        doc["audit"] = meta["audit"]
    if meta.get("source_refs"):
        doc["run"]["source_refs"] = meta["source_refs"]
    return doc


RUN_PREFIX = "security-run-"
# Sized for report_schema.MAX_FINDINGS (20000) at a few KB each. A smaller cap makes a large but valid scan
# unreadable for triage, verdict carry-over and the validator (a 7,000-finding scan is already ~7 MB).
MAX_REPORT_BYTES = 64 * 1024 * 1024


def read_report(path):
    """(document, errors): a v2 report that passes the validator and [], or None and why it cannot be used."""
    import json
    import os
    import report_schema
    try:
        size = os.path.getsize(str(path))
        if size > MAX_REPORT_BYTES:
            return None, ["%d bytes, larger than the %d-byte limit" % (size, MAX_REPORT_BYTES)]
        with open(str(path), "r", encoding="utf-8") as fh:
            doc = json.load(fh)
    except (OSError, ValueError) as exc:
        return None, [str(exc)]
    if not isinstance(doc, dict):
        return None, ["report must be a JSON object"]
    errors = report_schema.validate(doc)
    return (None, errors) if errors else (doc, [])


def load_report(path):
    """A v2 report that passes the validator, or None (missing, too big, not JSON, v1, invalid)."""
    return read_report(path)[0]


def find_previous(run_dir):
    """(document, folder) of the newest earlier security-run-* sibling with a valid v2 report, else (None, None).
    "Earlier" is by folder name, which sorts by the run's date and time."""
    from pathlib import Path
    run_dir = Path(run_dir).resolve()
    try:
        siblings = [p for p in run_dir.parent.iterdir()
                    if p.is_dir() and p.name.startswith(RUN_PREFIX) and p.name < run_dir.name]
    except OSError:
        return None, None
    for p in sorted(siblings, key=lambda x: x.name, reverse=True):
        doc = load_report(p / "security-report.json")
        if doc is not None:
            return doc, p
    return None, None


def keep_verdicts(doc, existing):
    """Copy verdicts of this run's earlier report onto the regenerated document (same fingerprints), then
    recompute counts. Findings that already carry a verdict (the deep audit's) are left as they are."""
    if not existing:
        return doc
    old = dict((p["fingerprint"], p) for p in existing.get("findings", []) if p.get("verdict"))
    for f in doc["findings"]:
        p = old.get(f["fingerprint"])
        if p and not f.get("verdict"):
            f["verdict"], f["verified_severity"] = p["verdict"], p.get("verified_severity")
            f["verdict_detail"], f["carried"] = p.get("verdict_detail") or {}, bool(p.get("carried"))
    return refresh(doc)


def refresh(doc):
    """Recompute derived fields after verdicts change (counts, repo summaries, verification)."""
    doc["counts"] = counts_of(doc["findings"])
    doc["repos"] = repo_summaries(doc["findings"], [r["name"] for r in doc.get("repos", [])])
    doc["verification"] = verification_summary(doc["findings"], (doc.get("run") or {}).get("profile"))
    return doc
