"""safegit.py - run git on a scanned repo without letting the repo's own config run programs.

A scanned repo may be untrusted, and its .git/config can name commands that git runs for it (core.fsmonitor on
any index refresh, hooks, diff.external). Every git call on a scanned repo goes through argv() and env().
Stdlib only; Python 3.8+.
"""

import os

SAFE = ["-c", "core.fsmonitor=false", "-c", "core.hooksPath=" + os.devnull, "-c", "diff.external=",
        "-c", "core.untrackedCache=false"]


def argv(path, *args):
    return ["git", "-C", path] + SAFE + list(args)


def env():
    return dict(os.environ, GIT_PAGER="cat", GIT_TERMINAL_PROMPT="0", GIT_OPTIONAL_LOCKS="0")
