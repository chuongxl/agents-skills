#!/usr/bin/env python3
"""fetch-iocs.py - refresh the Shai-Hulud indicator file from remote lists.

Usage:
  python3 -I scripts/fetch-iocs.py --out DIR [--sources assets/ioc/sources.json] [--base FILE]

Merges every source in the sources file into a copy of the committed indicator file and writes
DIR/shai-hulud.json. run-scan.sh uses <output-dir>/.ioc-cache/shai-hulud.json when it exists.
The committed file is never modified.

Exit codes: 0 all sources merged, 3 some source failed (the rest is still written),
            1 merged result invalid (nothing written), 2 usage.
This is the only part of the scanner that touches the network. Stdlib only; honours HTTPS_PROXY.
"""

import argparse
import csv
import io
import json
import os
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))

from shaihulud import iocs  # noqa: E402

TIMEOUT = 60
MAX_BYTES = 20 * 1024 * 1024


def fetch_text(url):
    req = urllib.request.Request(url, headers={"User-Agent": "job-security-scan/fetch-iocs"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:  # nosec - URLs come from the committed sources file
        data = resp.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError("response larger than %d bytes" % MAX_BYTES)
    return data.decode("utf-8-sig", errors="replace")


def parse_csv_name_versions(text):
    """Rows of (name, [versions]) from 'package_name' + 'package_versions' or 'package_version' columns."""
    rows = []
    for row in csv.DictReader(io.StringIO(text)):
        name = (row.get("package_name") or "").strip()
        raw = row.get("package_versions") or row.get("package_version") or ""
        versions = [v.strip() for v in raw.split(",") if v.strip()]
        if name and versions:
            rows.append((name, versions))
    return rows


PARSERS = {"csv-name-versions": parse_csv_name_versions}


def merge(data, source, rows):
    eco, wave = source["ecosystem"], source["wave"]
    index = {}
    for p in data["packages"]:
        index[(p["ecosystem"], iocs.normalize_name(p["ecosystem"], p["name"]))] = p
    added = 0
    for name, versions in rows:
        key = (eco, iocs.normalize_name(eco, name))
        entry = index.get(key)
        if entry is None:
            entry = {"ecosystem": eco, "name": name, "versions": [], "wave": wave, "sources": []}
            data["packages"].append(entry)
            index[key] = entry
        for v in versions:
            if v not in entry["versions"]:
                entry["versions"].append(v)
                added += 1
        if source["id"] not in entry.setdefault("sources", []):
            entry["sources"].append(source["id"])
    return added


def main(argv=None):
    ap = argparse.ArgumentParser(description="Refresh Shai-Hulud indicators from remote lists.")
    ap.add_argument("--out", required=True, help="directory to write shai-hulud.json into")
    ap.add_argument("--sources", default=str(iocs.ASSET_DIR / "sources.json"))
    ap.add_argument("--base", default=str(iocs.DEFAULT_IOCS), help="indicator file to start from")
    args = ap.parse_args(argv)

    data = json.loads(Path(args.base).read_text(encoding="utf-8"))
    sources = json.loads(Path(args.sources).read_text(encoding="utf-8")).get("sources", [])
    failed = []
    for src in sources:
        parser = PARSERS.get(src.get("format"))
        if parser is None:
            failed.append("%s: unknown format %r" % (src.get("id"), src.get("format")))
            continue
        try:
            rows = parser(fetch_text(src["url"]))
        except Exception as exc:  # network, HTTP, decode: report and keep going
            failed.append("%s: %s" % (src.get("id"), exc))
            continue
        added = merge(data, src, rows)
        print("  %-28s %5d packages read, %4d new versions" % (src["id"], len(rows), added))

    errors = iocs.validate(data)
    if errors:
        sys.stderr.write("merged indicator file is invalid, nothing written:\n  %s\n" % "\n  ".join(errors[:20]))
        return 1
    out = Path(args.out) / "shai-hulud.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8")
    os.replace(str(tmp), str(out))
    total = sum(len(p["versions"]) for p in data["packages"])
    print("  wrote %s (%d packages, %d versions)" % (out, len(data["packages"]), total))
    for line in failed:
        sys.stderr.write("  source failed - %s\n" % line)
    return 3 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
