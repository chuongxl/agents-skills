#!/usr/bin/env python3
"""changed-files.py - files changed since a git ref, per repo, for run-scan.sh --since.

Usage: python3 -I scripts/changed-files.py --since REF --repos-root DIR --out FILE REPO [REPO ...]

Writes {repo: [paths relative to the repo folder]} — committed changes in REF...HEAD plus staged, unstaged and
untracked working-tree files. A repo that cannot be scoped (not a git repo, unknown ref, no merge base) maps to
null and keeps its full scope; a warning says so.

The scanned repos may be untrusted, so git runs with an argument list (no shell), with the repo's hooks,
fsmonitor and external diff/textconv programs turned off, and with a timeout.
Stdlib only; Python 3.8+.
"""

import argparse
import json
import os
import re
import subprocess
import sys

REF_RE = re.compile(r"^[A-Za-z0-9._/~^@{}+-]{1,200}$")
SAFE = ["-c", "core.fsmonitor=false", "-c", "core.hooksPath=" + os.devnull, "-c", "diff.external=",
        "-c", "core.untrackedCache=false"]
MAX_FILES = 50000


def valid_ref(ref):
    return bool(REF_RE.match(ref or "")) and not ref.startswith("-")


def _git(path, *args):
    env = dict(os.environ, GIT_PAGER="cat", GIT_TERMINAL_PROMPT="0", GIT_OPTIONAL_LOCKS="0")
    r = subprocess.run(["git", "-C", path] + SAFE + list(args), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                       env=env, timeout=60)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.decode("utf-8", "replace").strip().splitlines()[-1:] or ["git failed"])
    return [p for p in r.stdout.decode("utf-8", "surrogateescape").split("\0") if p]


def changed(path, ref):
    """Set of changed paths relative to `path`, or raise RuntimeError with the reason."""
    inside = _git(path, "rev-parse", "--is-inside-work-tree")
    if not inside or inside[0].strip() != "true":
        raise RuntimeError("not a git work tree")
    try:
        _git(path, "rev-parse", "--verify", "--quiet", "--end-of-options", ref + "^{commit}")
    except RuntimeError:
        raise RuntimeError("no commit named %s in this repo" % ref)
    files = set()
    diff = ["diff", "--name-only", "-z", "--relative", "--no-ext-diff", "--no-textconv"]
    files.update(_git(path, *(diff + [ref + "...HEAD", "--"])))
    files.update(_git(path, *(diff + ["HEAD", "--"])))
    files.update(_git(path, "ls-files", "--others", "--exclude-standard", "-z"))
    if len(files) > MAX_FILES:
        raise RuntimeError("more than %d changed files" % MAX_FILES)
    return files


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--since", required=True)
    ap.add_argument("--repos-root", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("repos", nargs="*")
    a = ap.parse_args(argv)
    if not valid_ref(a.since):
        print("changed-files: invalid git ref %r" % a.since, file=sys.stderr)
        return 1
    out = {}
    for repo in a.repos:
        path = os.path.join(a.repos_root, repo)
        try:
            files = sorted(changed(path, a.since))
            out[repo] = files
            print("  [since] %s: %d file(s) changed since %s" % (repo, len(files), a.since))
        except (RuntimeError, OSError, subprocess.TimeoutExpired, IndexError) as exc:
            out[repo] = None
            reason = exc.args[0] if exc.args else type(exc).__name__
            if isinstance(reason, list):
                reason = reason[0] if reason else "git failed"
            print("  🟡 [since] %s: cannot scope to %s (%s) - full scope for this repo" % (repo, a.since, reason))
    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2)
        fh.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
