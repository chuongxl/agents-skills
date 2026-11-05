#!/usr/bin/env python3
"""validate-report.py - check a security-report.json (schema v2) against the report contract.

Usage: python3 -I scripts/validate-report.py security-run-YYYYMMDD-HHMMSS/security-report.json

Exit codes: 0 valid, 1 invalid (errors on stdout, at most 100), 2 usage or unreadable file.
Success proves format and internal consistency only, not that the findings are right.
Stdlib only; Python 3.8+.
"""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))

import report_schema  # noqa: E402
from report_model import MAX_REPORT_BYTES as MAX_BYTES  # noqa: E402


def main(argv):
    if len(argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    path = argv[1]
    try:
        if os.path.getsize(path) > MAX_BYTES:
            print("INVALID  %s: larger than %d bytes" % (path, MAX_BYTES))
            return 1
        with open(path, "r", encoding="utf-8") as fh:
            doc = json.load(fh)
    except OSError as exc:
        print("validate-report: %s" % exc, file=sys.stderr)
        return 2
    except ValueError as exc:
        print("INVALID  %s: not JSON: %s" % (path, exc))
        return 1
    errors = report_schema.validate(doc)
    if errors:
        print("INVALID  %s (%d error%s)" % (path, len(errors), "" if len(errors) == 1 else "s"))
        for e in errors:
            print("  - %s" % e)
        return 1
    print("VALID    %s (%d findings)" % (path, len(doc.get("findings", []))))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
