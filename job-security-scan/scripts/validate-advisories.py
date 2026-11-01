#!/usr/bin/env python3
"""validate-advisories.py - validate advisory bundles and the trusted-source registry.

Usage:
  python3 -I scripts/validate-advisories.py [PATH ...] [--strict] [--check-sources] [--json]
                                            [--sources FILE] [--schema FILE] [--timeout SECONDS]

PATH is a bundle file or a directory (searched recursively); default is assets/advisories plus assets/advisory-examples.

Exit codes:
  0  everything valid (and every source reachable when --check-sources is used)
  1  validation errors in advisories or sources.json
  2  usage error or unreadable input
  3  --check-sources: one or more source URLs unreachable (validation itself passed)

Stdlib only; Python 3.8+. Run with -I (isolated mode) - this script adds only its own
lib/ directory to the import path.
"""

import argparse
import json
import os
import sys

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(SKILL_DIR, "scripts", "lib"))

import advisory  # noqa: E402
import sources  # noqa: E402


def _display(path):
    """Relative path when possible, so every message prints paths the same way."""
    try:
        return os.path.relpath(path)
    except ValueError:  # different drive on Windows
        return path


def main(argv=None):
    ap = argparse.ArgumentParser(description="Validate advisory bundles and sources.json")
    ap.add_argument("paths", nargs="*", help="bundle files or directories (default: assets/advisories and assets/advisory-examples)")
    ap.add_argument("--sources", default=os.path.join(SKILL_DIR, "assets", "sources.json"))
    ap.add_argument("--schema", default=os.path.join(SKILL_DIR, "assets", "advisory.schema.json"))
    ap.add_argument("--strict", action="store_true", help="treat warnings (e.g. unapproved llm-assisted data) as errors")
    ap.add_argument("--check-sources", action="store_true", help="live-check every URL in sources.json")
    ap.add_argument("--timeout", type=float, default=20.0, help="per-URL timeout for --check-sources")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args(argv)

    paths = args.paths or [os.path.join(SKILL_DIR, "assets", d) for d in ("advisories", "advisory-examples")]
    paths = [_display(p) for p in paths]

    try:
        schema = advisory.load_json(args.schema)
        src_data = sources.load_sources(args.sources)
    except advisory.AdvisoryError as exc:
        print("ERROR: %s" % exc, file=sys.stderr)
        return 2

    src_errors = sources.validate_sources(src_data)
    allowed = sources.allowed_hosts_of(src_data)

    try:
        results = advisory.validate_paths(paths, schema, allowed or None, args.strict)
    except advisory.AdvisoryError as exc:
        print("ERROR: %s" % exc, file=sys.stderr)
        return 2

    if not results:
        print("ERROR: no advisory files found under: %s" % ", ".join(paths), file=sys.stderr)
        return 2

    checks = None
    if args.check_sources:
        if src_errors:
            print("NOTE   skipping --check-sources: sources.json has errors; fix them first", file=sys.stderr)
        else:
            checks = sources.check_sources(src_data, timeout=args.timeout)

    n_err = len(src_errors) + sum(len(r["errors"]) for r in results)
    n_warn = sum(len(r["warnings"]) for r in results)
    unreachable = [c for c in (checks or []) if not c["ok"]]

    if args.json:
        print(json.dumps({
            "sources_errors": src_errors,
            "files": results,
            "source_checks": checks,
            "errors": n_err,
            "warnings": n_warn,
            "unreachable": len(unreachable),
        }, indent=2))
    else:
        for e in src_errors:
            print("ERROR  %s: %s" % (args.sources, e))
        for r in results:
            for e in r["errors"]:
                print("ERROR  %s" % e)
            for w in r["warnings"]:
                print("WARN   %s" % w)
            if not r["errors"]:
                print("OK     %s (%d advisories)" % (os.path.relpath(r["file"]), len(r["ids"])))
        if checks is not None:
            for c in checks:
                mark = "OK  " if c["ok"] else "FAIL"
                print("%s   %-10s %-14s %s %s" % (mark, c["group"], c["id"], c["url"],
                                                  "" if c["ok"] else "(%s)" % c["note"]))
        print("%d file(s), %d error(s), %d warning(s)%s" % (
            len(results), n_err, n_warn,
            ", %d/%d source(s) unreachable" % (len(unreachable), len(checks)) if checks is not None else ""))

    if n_err:
        return 1
    if unreachable:
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
