"""Remove secret values from raw scanner output before it is kept in a security-run folder.

TruffleHog has no redact option: each JSON line carries the found secret in "Raw" / "RawV2" (and sometimes
in ExtraData). The report needs where and what kind, never the value, so those fields are removed in place.

Semgrep secret rules put the matched text in extra.lines and in extra.metavars[*].abstract_content, and Trivy's
JSON carries a Match and code lines for each secret: those fields are blanked, location and rule stay.

Usage: python3 -I scripts/lib/sanitize.py trufflehog|semgrep|trivy FILE
Stdlib only; Python 3.8+.
"""

import json
import os
import re
import sys

TRUFFLEHOG_SECRET_KEYS = ("Raw", "RawV2")

_REDACTIONS = [
    (re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----.*?(?:-----END [A-Z0-9 ]*PRIVATE KEY-----|$)", re.S),
     "[private key redacted]"),
    (re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}"), "github_pat_***"),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}"), "gh_***"),
    (re.compile(r"\bnpm_[A-Za-z0-9]{20,}"), "npm_***"),
    (re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"), "AKIA***"),
    (re.compile(r"(_authToken|_auth|_password)\s*=\s*\S+"), r"\1=***"),
    (re.compile(r"(?i)((?:secret|token|passw(?:or)?d|api[_-]?key|access[_-]?key|credential)[\w.-]{0,30}\s*[=:]\s*)"
                r"[\"']?[^\s\"',;]{8,}"), r"\1***"),
    (re.compile(r"([=:]\s*[\"']?)[A-Za-z0-9+/=_-]{32,}"), r"\1***"),
    (re.compile(r"[A-Za-z0-9+/=_-]{40,}"), "***"),
]


def redact(text):
    """Mask token-shaped text, collapse whitespace and cap the result."""
    if not text:
        return ""
    for pattern, replacement in _REDACTIONS:
        text = pattern.sub(replacement, text)
    text = " ".join(text.split())
    return text if len(text) <= 120 else text[:117] + "..."


def strip_trufflehog(path):
    """Rewrite a TruffleHog JSON-lines file without secret values. Returns the number of findings kept."""
    kept = []
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except ValueError:
                continue  # never keep a line we cannot clean
            if not isinstance(row, dict):
                continue
            for key in TRUFFLEHOG_SECRET_KEYS:
                row.pop(key, None)
            if isinstance(row.get("ExtraData"), dict):
                row["ExtraData"] = dict((k, v) for k, v in row["ExtraData"].items()
                                        if not any(s in k.lower() for s in ("token", "secret", "key", "password")))
            kept.append(json.dumps(row, separators=(",", ":")))
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write("\n".join(kept) + ("\n" if kept else ""))
    os.replace(tmp, path)
    return len(kept)


def semgrep_is_secret(item):
    """Secret-detection rules (p/secrets, *.secrets.* ids, or metadata saying so)."""
    check_id = str(item.get("check_id", "")).lower()
    if ".secrets." in check_id or check_id.startswith("secrets.") or "hardcoded-secret" in check_id:
        return True
    meta = (item.get("extra") or {}).get("metadata") or {}
    tags = []
    for key in ("category", "subcategory", "technology", "cwe"):
        v = meta.get(key)
        tags += v if isinstance(v, list) else [v]
    return any(isinstance(t, str) and ("secret" in t.lower() or "CWE-798" in t) for t in tags)


def _rewrite(path, doc):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(doc, fh)
    os.replace(tmp, path)


def strip_semgrep(path):
    """Blank the matched text of every secret-rule result in a Semgrep JSON file. Returns the number blanked."""
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        doc = json.load(fh)
    n = 0
    for item in doc.get("results", []) if isinstance(doc, dict) else []:
        if isinstance(item, dict) and semgrep_is_secret(item):
            extra = item.get("extra")
            if isinstance(extra, dict):
                extra["lines"] = ""
                if "metavars" in extra:
                    extra["metavars"] = {}
                if "fingerprint" in extra:
                    extra["fingerprint"] = ""
                n += 1
    _rewrite(path, doc)
    return n


def strip_trivy(path):
    """Drop Match and code lines from every secret in a Trivy JSON file. Returns the number cleaned."""
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        doc = json.load(fh)
    n = 0
    for result in doc.get("Results", []) if isinstance(doc, dict) else []:
        for s in result.get("Secrets", []) if isinstance(result, dict) else []:
            if isinstance(s, dict):
                s.pop("Match", None)
                s.pop("Code", None)
                n += 1
    _rewrite(path, doc)
    return n


def main(argv):
    modes = {"trufflehog": strip_trufflehog, "semgrep": strip_semgrep, "trivy": strip_trivy}
    if len(argv) != 3 or argv[1] not in modes:
        print(__doc__, file=sys.stderr)
        return 2
    print(modes[argv[1]](argv[2]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
