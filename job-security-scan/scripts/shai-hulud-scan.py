#!/usr/bin/env python3
"""shai-hulud-scan.py - quick check for the Shai-Hulud npm/PyPI worm family.

Usage:
  python3 -I scripts/shai-hulud-scan.py --repo PATH [--output FILE] [--format text|json] [--iocs FILE]
  python3 -I scripts/shai-hulud-scan.py --host [--root PATH ...] [--max-depth N] [--output FILE]

Repo mode checks one directory tree. Host mode checks this computer: projects under the roots
(default: your home directory), global installs, the npm cache, and lists credential stores
(never their contents).

Exit codes: 0 clean, 1 suspicious (worm-like behaviour, no known indicator),
            2 affected (known indicator found), 3 usage or I/O error.
Offline: never runs npm/node/pip, never touches the network. Stdlib only.
"""

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))

from shaihulud import findings, iocs, scanner  # noqa: E402

EXIT_USAGE = 3


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        self.print_usage(sys.stderr)
        sys.stderr.write("%s: error: %s\n" % (self.prog, message))
        sys.exit(EXIT_USAGE)


def parse_args(argv):
    ap = _Parser(description="Detect Shai-Hulud supply-chain worm indicators in a repo or on this computer.")
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--repo", help="directory to scan")
    mode.add_argument("--host", action="store_true", help="scan this computer")
    ap.add_argument("--root", action="append", default=[], help="host mode: directory to search (repeatable; default $HOME)")
    ap.add_argument("--max-depth", type=int, default=8, help="host mode: directory depth limit (default 8)")
    ap.add_argument("--iocs", help="indicator file (default: $SHAI_HULUD_IOCS or assets/ioc/shai-hulud.json)")
    ap.add_argument("--output", help="write the JSON result here")
    ap.add_argument("--format", choices=("text", "json"), default="text", help="stdout format (default text)")
    return ap.parse_args(argv)


def run(args):
    ioc = iocs.load(args.iocs)
    allowlist = iocs.load_allowlist()
    if args.host:
        from shaihulud import host
        home = Path.home()
        roots = [Path(r).expanduser() for r in args.root] or [home]
        for r in roots:
            if not r.is_dir():
                raise IOError("root is not a directory: %s" % r)
        found = host.scan_host(roots, home, ioc, allowlist, max_depth=args.max_depth)
        doc = findings.to_document("host", ", ".join(str(r) for r in roots), ioc.version, found)
    else:
        root = Path(args.repo)
        if not root.is_dir():
            raise IOError("not a directory: %s" % root)
        found = scanner.scan_repo(root, ioc, allowlist)
        doc = findings.to_document("repo", str(root), ioc.version, found)
    return doc


def main(argv=None):
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        doc = run(args)
    except (IOError, OSError, ValueError) as exc:
        sys.stderr.write("shai-hulud-scan: %s\n" % exc)
        return EXIT_USAGE
    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        tmp = out.with_suffix(out.suffix + ".tmp")
        tmp.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
        os.replace(str(tmp), str(out))
    if args.format == "json":
        sys.stdout.write(json.dumps(doc, indent=2) + "\n")
    else:
        sys.stdout.write(findings.to_text(doc))
        if doc["mode"] == "host":
            sys.stdout.write("Also check your GitHub account for repos and workflows the worm creates: "
                             "see references/remediation.md (Shai-Hulud: if affected).\n")
    return findings.exit_code(doc["verdict"])


if __name__ == "__main__":
    sys.exit(main())
