#!/usr/bin/env python3
"""validate-report.py - check a run's security report (schema v3 index + shards, or a v2 file) against the
report contract.

Usage: python3 -I scripts/validate-report.py security-run-YYYYMMDD-HHMMSS
       python3 -I scripts/validate-report.py security-run-YYYYMMDD-HHMMSS/security-report.json
       python3 -I scripts/validate-report.py any-report.json      (a single file with findings inline)

Every shard is checked against the size and sha256 the index records, then the whole report is validated.
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
import report_store   # noqa: E402


def _single_file(path):
    """A report file outside the run layout (findings inline): (doc, None) or raise ReportError."""
    if os.path.getsize(str(path)) > report_store.MAX_V2_FILE:
        raise report_store.ReportTooLarge("%s is larger than %d bytes" % (path, report_store.MAX_V2_FILE))
    with open(str(path), "r", encoding="utf-8") as fh:
        try:
            return json.load(fh)
        except ValueError as exc:
            raise report_store.ReportCorrupt("%s: not JSON: %s" % (path, exc))


def main(argv):
    if len(argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    path = Path(argv[1])
    if not path.exists():
        print("validate-report: %s does not exist" % path, file=sys.stderr)
        return 2
    run_dir = path if path.is_dir() else path.parent
    try:
        if path.is_dir() or path.name == report_store.INDEX_NAME:
            index = report_store.load_index(run_dir)
            if index.get("schema_version") == 3:
                doc = report_store.load_full(run_dir)
                print("VALID    %s (%d findings, %d shards)" % (path, len(doc["findings"]), len(index["shards"])))
                return 0
            doc = index
        else:
            doc = _single_file(path)
    except report_store.ReportError as exc:
        print("INVALID  %s: %s" % (path, exc))
        return 1
    except OSError as exc:
        print("validate-report: %s" % exc, file=sys.stderr)
        return 2
    errors = report_schema.validate(doc)
    if errors:
        print("INVALID  %s (%d error%s)" % (path, len(errors), "" if len(errors) == 1 else "s"))
        for e in errors:
            print("  - %s" % e)
        return 1
    print("VALID    %s (%d findings, 0 shards)" % (path, len(doc.get("findings", []))))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
