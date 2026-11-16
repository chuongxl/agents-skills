"""safegit.py - run git against a repository we do not trust.

A scanned repo may ship its own .git/config. Git reads commands out of it (core.fsmonitor, core.sshCommand,
core.pager, hooks via core.hooksPath, diff.external, credential helpers, gpg.program ...), so a plain
`git status` in a hostile checkout can run code. Every call here overrides those keys on the command line, which
beats repo config, uses an argument list (no shell), turns off prompts and optional locks, and has a timeout.

Residual: a repo-defined `diff.<driver>.textconv` command selected through .gitattributes cannot be switched off
globally; callers that only read metadata (rev-parse, status, ls-files, diff --name-only) never reach it, and
the history scanners (Gitleaks, TruffleHog) are the known remaining exposure - see SKILL.md "Security of the skill".
Stdlib only; Python 3.8+.
"""
import os
import subprocess

# key=value pairs forced over the repository's own configuration
OVERRIDES = (
    ("core.fsmonitor", "false"),
    ("core.hooksPath", os.devnull),
    ("core.sshCommand", "false"),
    ("core.pager", "cat"),
    ("core.untrackedCache", "false"),
    ("diff.external", ""),
    ("credential.helper", ""),
    ("gpg.program", "false"),
    ("protocol.ext.allow", "never"),
    ("protocol.file.allow", "user"),
)


def config_args():
    """['-c', 'k=v', ...] for a git command line."""
    out = []
    for k, v in OVERRIDES:
        out += ["-c", "%s=%s" % (k, v)]
    return out


def env(base=None):
    """Environment for a git child: same overrides through GIT_CONFIG_COUNT (reaches tools that spawn git),
    no prompts, no pager, no optional locks, no system/global config."""
    e = dict(os.environ if base is None else base)
    e.update({"GIT_TERMINAL_PROMPT": "0", "GIT_PAGER": "cat", "GIT_OPTIONAL_LOCKS": "0",
              "GIT_CONFIG_NOSYSTEM": "1", "GIT_ASKPASS": "true", "GIT_CONFIG_COUNT": str(len(OVERRIDES))})
    for i, (k, v) in enumerate(OVERRIDES):
        e["GIT_CONFIG_KEY_%d" % i] = k
        e["GIT_CONFIG_VALUE_%d" % i] = v
    return e


def run(path, *args, **kw):
    """subprocess.run(['git', '-C', path, <overrides>, *args]); returns the CompletedProcess."""
    kw.setdefault("timeout", 60)
    kw.setdefault("stdout", subprocess.PIPE)
    kw.setdefault("stderr", subprocess.PIPE)
    return subprocess.run(["git", "-C", path] + config_args() + list(args), env=env(), **kw)


def text(path, *args):
    """stdout of a successful git command, else None (git missing, timeout or non-zero exit)."""
    try:
        r = run(path, *args, universal_newlines=True)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return r.stdout if r.returncode == 0 else None
