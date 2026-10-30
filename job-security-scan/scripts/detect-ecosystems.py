#!/usr/bin/env python3
"""detect-ecosystems.py - detect the languages/ecosystems used by a repository.

Usage:
  python3 -I scripts/detect-ecosystems.py PATH [--format summary|json|lockfiles|semgrep|ids|needs-sbom]
                                          [--ecosystems DIR] [--max-depth N]
  python3 -I scripts/detect-ecosystems.py --validate [--ecosystems DIR]

Formats:
  summary     human-readable table (default)
  json        full detection result
  lockfiles   one lockfile path per line, relative to PATH
  semgrep     one Semgrep ruleset id per line
  ids         one ecosystem id per line
  needs-sbom  prints 'true' or 'false'

Exit codes: 0 ok, 2 usage error or invalid descriptors.
Stdlib only; Python 3.8+. Run with -I.
"""

import argparse
import json
import os
import sys

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(SKILL_DIR, "scripts", "lib"))

import ecosystems  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser(description="Detect repository ecosystems")
    ap.add_argument("path", nargs="?", help="repository directory")
    ap.add_argument("--format", default="summary",
                    choices=["summary", "json", "lockfiles", "semgrep", "ids", "needs-sbom"])
    ap.add_argument("--ecosystems", default=ecosystems.default_dir(), help="descriptor directory")
    ap.add_argument("--max-depth", type=int, default=ecosystems.DEFAULT_MAX_DEPTH)
    ap.add_argument("--validate", action="store_true", help="only validate the descriptors")
    args = ap.parse_args(argv)

    try:
        descriptors = ecosystems.load_descriptors(args.ecosystems)
    except ecosystems.EcosystemError as exc:
        print("ERROR: invalid ecosystem descriptors:\n%s" % exc, file=sys.stderr)
        return 2

    if args.validate:
        print("OK     %d ecosystem descriptor(s): %s" % (len(descriptors), ", ".join(d["id"] for d in descriptors)))
        return 0
    if not args.path:
        ap.error("PATH is required unless --validate is used")

    try:
        result = ecosystems.detect(args.path, descriptors, args.max_depth)
    except ecosystems.EcosystemError as exc:
        print("ERROR: %s" % exc, file=sys.stderr)
        return 2

    fmt = args.format
    if fmt == "json":
        print(json.dumps(result, indent=2))
    elif fmt == "lockfiles":
        print("\n".join(result["lockfiles"]))
    elif fmt == "semgrep":
        print("\n".join(result["semgrep"]))
    elif fmt == "ids":
        print("\n".join(e["id"] for e in result["ecosystems"]))
    elif fmt == "needs-sbom":
        print("true" if result["needs_sbom"] else "false")
    else:
        if not result["ecosystems"]:
            print("No known ecosystem detected - the SBOM fallback will be used.")
        for e in result["ecosystems"]:
            print("%-12s %s" % (e["id"], e["name"]))
            print("  manifests : %s" % (", ".join(e["manifests"]) or "-"))
            print("  lockfiles : %s" % (", ".join(e["lockfiles"]) or "- (SBOM fallback)"))
        print("SBOM fallback needed: %s" % ("yes" if result["needs_sbom"] else "no"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
