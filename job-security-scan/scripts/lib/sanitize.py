"""Remove secret values from raw scanner output before it is kept in a security-run folder.

TruffleHog has no redact option: each JSON line carries the found secret in "Raw" / "RawV2" (and sometimes
in ExtraData). The report needs where and what kind, never the value, so those fields are removed in place.

Usage: python3 -I scripts/lib/sanitize.py trufflehog FILE
Stdlib only; Python 3.8+.
"""

import json
import os
import sys

TRUFFLEHOG_SECRET_KEYS = ("Raw", "RawV2")


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


def main(argv):
    if len(argv) != 3 or argv[1] != "trufflehog":
        print(__doc__, file=sys.stderr)
        return 2
    print(strip_trufflehog(argv[2]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
