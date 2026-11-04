#!/usr/bin/env python3
"""assert-findings.py - check that an osv-scanner JSON report contains an expected finding.

Usage: python3 -I tests/e2e/assert-findings.py REPORT.json PACKAGE VULN_ID [VULN_ID ...]

Passes when PACKAGE (case-insensitive) is reported with at least one of the VULN_IDs,
matched against the vulnerability id or any of its aliases. Exit 0 pass, 1 fail, 2 usage.
"""
import json
import sys


def main(argv):
    if len(argv) < 4:
        print(__doc__, file=sys.stderr)
        return 2
    report, package, wanted = argv[1], argv[2].lower(), set(argv[3:])
    with open(report, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    seen = {}
    for res in data.get("results", []):
        for pkg in res.get("packages", []):
            name = pkg.get("package", {}).get("name", "").lower()
            ids = seen.setdefault(name, set())
            for v in pkg.get("vulnerabilities", []):
                ids.add(v.get("id", ""))
                ids.update(v.get("aliases", []))
    hit = seen.get(package, set()) & wanted
    if hit:
        print("PASS  %s: %s" % (package, ", ".join(sorted(hit))))
        return 0
    print("FAIL  %s: expected one of %s; ids reported for it: %s; packages with findings: %s" % (
        package, sorted(wanted), sorted(seen.get(package, set())) or "none", sorted(k for k, v in seen.items() if v)))
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
