"""Finding model, secret redaction, verdict and output for the Shai-Hulud detector."""

import hashlib
import re

SEVERITIES = ("CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO")
TIERS = ("affected", "suspicious", "exposure")
EVIDENCE_MAX = 120
MASK = "***"

REMEDIATION = {
    "known-package": "A release published by the worm is present. Treat every machine and CI runner that "
                     "installed it as compromised: follow the 'If affected' runbook in references/remediation.md, "
                     "then pin a clean version and reinstall from a clean lockfile.",
    "payload-file": "The worm's payload or stager file is on disk. Do not run installs here. Isolate the machine or "
                    "runner, delete node_modules and the npm cache, and rotate credentials (runbook).",
    "planted-path": "A file the worm plants for persistence or exfiltration is present. Delete it in a reviewed "
                    "commit, check git history for who added it, and rotate the credentials it could reach.",
    "marker": "A string unique to the worm (runner label, repo description, C2 host) was found. Investigate the file "
              "and the account or runner it refers to; follow the runbook.",
    "hook-exfil": "An install hook runs code that reads credentials and sends data out. Do not install this package; "
                  "review the script, report it to the registry, and rotate anything it could read if it already ran.",
    "hook-pipe-shell": "An install hook pipes a download into a shell. Remove or pin the package; never run remote "
                       "scripts at install time.",
    "hook-obfuscated": "An install hook runs heavily obfuscated code. Review the package before installing; prefer "
                       "'npm install --ignore-scripts' until it is cleared.",
    "hook-runtime-download": "An install hook downloads a runtime or secret-scanning tool. This matches the worm's "
                             "behaviour; review the package before installing.",
    "large-hook-target": "An install-hook script is too large to scan. Review it manually or install with "
                         "--ignore-scripts.",
    "cached-package": "A worm release was downloaded on this machine (npm cache). If any project installed it, "
                      "follow the runbook; then run 'npm cache clean --force'.",
    "credential-store": "Credential store present. If this machine is affected, rotate it (runbook order: npm, "
                        "GitHub, cloud, SSH). Nothing to do if the verdict is clean.",
    "credential-permissions": "Credential file is readable by other users. Restrict it: chmod 600 (files) / "
                              "chmod 700 (directories).",
}

_REDACTIONS = [
    (re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----.*?(?:-----END [A-Z0-9 ]*PRIVATE KEY-----|$)", re.S),
     "[private key redacted]"),
    (re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}"), "github_pat_" + MASK),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}"), "gh_" + MASK),
    (re.compile(r"\bnpm_[A-Za-z0-9]{20,}"), "npm_" + MASK),
    (re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"), "AKIA" + MASK),
    (re.compile(r"(_authToken|_auth|_password)\s*=\s*\S+"), r"\1=" + MASK),
    (re.compile(r"(?i)((?:secret|token|passw(?:or)?d|api[_-]?key|access[_-]?key|credential)[\w.-]{0,30}\s*[=:]\s*)"
                r"[\"']?[^\s\"',;]{8,}"), r"\1" + MASK),
    (re.compile(r"([=:]\s*[\"']?)[A-Za-z0-9+/=_-]{32,}"), r"\1" + MASK),
    (re.compile(r"[A-Za-z0-9+/=_-]{40,}"), MASK),
]


def redact(text):
    """Mask anything token-shaped, collapse whitespace, cap at EVIDENCE_MAX chars."""
    if not text:
        return ""
    out = text
    for pattern, repl in _REDACTIONS:
        out = pattern.sub(repl, out)
    out = " ".join(out.split())
    if len(out) > EVIDENCE_MAX:
        out = out[:EVIDENCE_MAX - 3] + "..."
    return out


def make_finding(tier, severity, category, location, title, package="", version="", wave="", evidence="",
                 remediation_key=None):
    if tier not in TIERS:
        raise ValueError("unknown tier %r" % tier)
    if severity not in SEVERITIES:
        raise ValueError("unknown severity %r" % severity)
    key = remediation_key or category
    ident = hashlib.sha1("|".join((tier, category, location, package, version)).encode("utf-8")).hexdigest()[:12]
    return {
        "id": ident,
        "tier": tier,
        "severity": severity,
        "category": category,
        "location": location,
        "title": title,
        "package": package,
        "version": version,
        "wave": wave,
        "evidence": redact(evidence),
        "remediation": REMEDIATION.get(key, ""),
    }


def relocate(finding, prefix):
    """Copy of finding with location prefixed (e.g. '~/work/app') and its id recomputed."""
    f = dict(finding)
    loc = f["location"]
    f["location"] = prefix if loc in ("", ".") else "%s/%s" % (prefix.rstrip("/"), loc)
    f["id"] = hashlib.sha1("|".join((f["tier"], f["category"], f["location"], f["package"], f["version"]))
                           .encode("utf-8")).hexdigest()[:12]
    return f


def verdict(findings):
    tiers = {f["tier"] for f in findings}
    if "affected" in tiers:
        return "affected"
    if "suspicious" in tiers:
        return "suspicious"
    return "clean"


def exit_code(v):
    return {"clean": 0, "suspicious": 1, "affected": 2}[v]


def dedupe(findings):
    seen, out = set(), []
    for f in findings:
        if f["id"] not in seen:
            seen.add(f["id"])
            out.append(f)
    return out


def to_document(mode, target, ioc_version, findings):
    findings = sorted(dedupe(findings), key=lambda f: (SEVERITIES.index(f["severity"]), f["location"], f["category"]))
    counts = dict((s, 0) for s in SEVERITIES)
    for f in findings:
        counts[f["severity"]] += 1
    return {
        "scanner": "shai-hulud",
        "mode": mode,
        "target": target,
        "ioc_version": ioc_version,
        "verdict": verdict(findings),
        "counts": counts,
        "findings": findings,
    }


_HEADLINE = {
    "affected": "AFFECTED - known Shai-Hulud indicator found",
    "suspicious": "SUSPICIOUS - worm-like install behaviour found, no known indicator",
    "clean": "CLEAN - no Shai-Hulud indicator or suspicious install behaviour found",
}


def to_text(doc):
    lines = ["Shai-Hulud check (%s): %s" % (doc["mode"], doc["target"]),
             "Verdict: %s" % _HEADLINE[doc["verdict"]],
             "Indicators: %s   Counts: %s" % (doc["ioc_version"],
                                               " ".join("%s=%d" % (s, n) for s, n in doc["counts"].items() if n))]
    for f in doc["findings"]:
        what = "%s@%s" % (f["package"], f["version"]) if f["package"] else ""
        wave = " [%s]" % f["wave"] if f["wave"] else ""
        lines.append("  %-8s %-22s %s %s%s" % (f["severity"], f["category"], f["location"], what, wave))
        if f["evidence"]:
            lines.append("           evidence: %s" % f["evidence"])
    return "\n".join(lines) + "\n"
