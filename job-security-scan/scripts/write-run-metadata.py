#!/usr/bin/env python3
"""Write <run>/run-metadata.json: what this run scanned and at which source revision.

  python3 -I write-run-metadata.py --run-dir DIR --scanner all [--profile P] [--since REF] [--budget N] \
      [--host] --repo NAME=PATH [--repo NAME=PATH ...]

Records each repo's commit and whether its worktree was dirty, so the report can say exactly what was
reviewed and earlier/later runs can be compared honestly. Never reads file contents. Stdlib only.
"""
import argparse
import json
import os
import subprocess
from datetime import datetime


def source_ref(path):
    def git(*args):
        try:
            r = subprocess.run(["git", "-C", path] + list(args), capture_output=True, text=True, timeout=60)
        except (OSError, subprocess.TimeoutExpired):
            return None
        return r.stdout if r.returncode == 0 else None
    commit = git("rev-parse", "HEAD")
    if not commit:
        return {"commit": None, "dirty": None, "vcs": None}
    status = git("status", "--porcelain", "--untracked-files=normal")
    branch = git("rev-parse", "--abbrev-ref", "HEAD")
    return {"commit": commit.strip(), "dirty": bool(status.strip()) if status is not None else None,
            "branch": branch.strip() if branch else None, "vcs": "git"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--scanner", required=True)
    ap.add_argument("--profile", default="")
    ap.add_argument("--since", default="")
    ap.add_argument("--budget", default="")
    ap.add_argument("--host", action="store_true")
    ap.add_argument("--audit", action="store_true")
    ap.add_argument("--repo", action="append", default=[])
    args = ap.parse_args()
    refs = {}
    for item in args.repo:
        name, _, path = item.partition("=")
        refs[name] = source_ref(path) if os.path.isdir(path) else {"commit": None, "dirty": None, "vcs": None,
                                                                    "missing": True}
    doc = {"created_at": datetime.now().astimezone().isoformat(timespec="seconds"), "scanner": args.scanner,
           "audit": args.audit or args.scanner == "audit", "profile": args.profile or None,
           "since": args.since or None, "budget": int(args.budget) if args.budget.isdigit() else None,
           "host": args.host, "repos": sorted(refs), "source_refs": refs}
    with open(os.path.join(args.run_dir, "run-metadata.json"), "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2)
        fh.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
