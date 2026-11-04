#!/usr/bin/env python3
"""assert-located.py - check a security-report.json: every finding that points at a file has a line, and
no secret or credential row carries a code excerpt.

Usage: python3 -I tests/e2e/assert-located.py security-report.json [SCANNER]
With SCANNER, only that scanner's findings are checked (and at least one must exist).
Exit 0 pass, 1 fail, 2 usage.
"""
import json
import sys

NO_FILE_RULES = {"credential-store", "credential-permissions", "cached-package"}


def main(argv):
    if len(argv) not in (2, 3):
        print(__doc__, file=sys.stderr)
        return 2
    rows = json.load(open(argv[1], encoding="utf-8"))["findings"]
    if len(argv) == 3:
        rows = [f for f in rows if f["scanner"] == argv[2]]
    if not rows:
        print("FAIL  no findings to check")
        return 1
    unlocated = ["%s %s %s %s" % (f["repo"], f["scanner"], f["rule_id"], f["file"]) for f in rows
                 if f["file"] and f["rule_id"] not in NO_FILE_RULES and not f["line"]]
    leaked = ["%s %s %s" % (f["repo"], f["scanner"], f["rule_id"]) for f in rows
              if (f["type"] == "secret" or f["rule_id"] in NO_FILE_RULES) and f.get("code")]
    if unlocated or leaked:
        print("FAIL  without a line: %s; code on secret/credential rows: %s" % (unlocated[:10], leaked[:10]))
        return 1
    print("PASS  %d findings located" % len(rows))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
