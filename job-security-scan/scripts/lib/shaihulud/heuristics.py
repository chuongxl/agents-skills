"""Tier 2: install hooks that behave like the Shai-Hulud worm, without a known indicator.

A hook is reported only when signals combine (secret source + exfil sink), or when the command
itself is unambiguous (download piped into a shell). One weak signal on its own is never reported.
"""

import os
import re

from . import MAX_SCAN_BYTES
from .findings import make_finding
from .hooks import hook_target, install_hooks, read_text
from .iocs import is_allowed

PIPE_SHELL = re.compile(r"\b(?:curl|wget)\b[^|;&]*\|\s*(?:sudo\s+)?(?:ba|z|da)?sh\b")

SECRET_SOURCES = re.compile(
    r"\b(?:GITHUB_TOKEN|GH_TOKEN|NPM_TOKEN|NODE_AUTH_TOKEN|AWS_ACCESS_KEY_ID|AWS_SECRET_ACCESS_KEY|AWS_SESSION_TOKEN"
    r"|AZURE_[A-Z_]+|GCP_[A-Z_]+|GOOGLE_APPLICATION_CREDENTIALS|CI_JOB_TOKEN|ACTIONS_RUNTIME_TOKEN"
    r"|ACTIONS_ID_TOKEN_REQUEST_TOKEN)\b"
    r"|\.npmrc\b|\.ssh/id_|\.aws/credentials|\.git-credentials|\.config/gh/hosts|gcloud/credentials"
    r"|gh auth token|trufflehog"
    r"|JSON\.stringify\(\s*process\.env\s*\)|Object\.(?:keys|entries|values)\(\s*process\.env\s*\)",
    re.I)

EXFIL_SINKS = re.compile(
    r"\bfetch\s*\(|\baxios\b|\bhttps?\.(?:request|get)\s*\(|require\(\s*['\"](?:node:)?https?['\"]\s*\)\s*\.(?:request|get)"
    r"|\bXMLHttpRequest\b|\bnet\.connect\s*\(|api\.github\.com|\boctokit\b|webhook\.site"
    r"|\b(?:exec|execSync|spawn|spawnSync|execFile|execFileSync)\s*\(\s*['\"`]\s*(?:curl|wget|gh|trufflehog)\b")

OBFUSCATED_BLOB = re.compile(r"[A-Za-z0-9+/=]{2000,}|(?:\\x[0-9a-fA-F]{2}){500,}|[0-9a-fA-F]{2000,}")
DYNAMIC_EVAL = re.compile(r"\beval\s*\(|\bnew\s+Function\s*\(|\bFunction\s*\(")
RUNTIME_DOWNLOAD = re.compile(
    r"bun\.sh/install|github\.com/oven-sh/bun/releases"
    r"|trufflehog[^\n]{0,200}releases/download|releases/download[^\n]{0,200}trufflehog", re.I)


def _rel(root, path):
    return os.path.relpath(str(path), str(root)).replace(os.sep, "/")


def _snippet(text, match):
    start = max(0, match.start() - 30)
    return text[start:match.end() + 60]


def analyze_manifest(pkg_dir, manifest, allowlist, repo_root, ioc=None):
    """Tier-2 findings for one package's install hooks."""
    out = []
    name = manifest.get("name") if isinstance(manifest.get("name"), str) else ""
    version = manifest.get("version") if isinstance(manifest.get("version"), str) else ""

    def add(severity, category, location, title, evidence):
        out.append(make_finding("suspicious", severity, category, location, title,
                                package=name, version=version, evidence=evidence))

    manifest_loc = _rel(repo_root, os.path.join(str(pkg_dir), "package.json"))
    for hook, command in install_hooks(manifest):
        if is_allowed(allowlist, command, name):
            continue
        if PIPE_SHELL.search(command):
            add("HIGH", "hook-pipe-shell", manifest_loc, "Install hook '%s' pipes a download into a shell" % hook,
                command)
        target = hook_target(pkg_dir, command)
        if target is None:
            continue
        if ioc is not None and target.name in ioc.files and not ioc.files[target.name]["sha256"]:
            continue  # a listed payload: tier 1 already reports it
        loc = _rel(repo_root, target)
        try:
            size = os.path.getsize(str(target))
        except OSError:
            continue
        if size > MAX_SCAN_BYTES:
            add("LOW", "large-hook-target", loc, "Install hook '%s' runs a file too large to scan" % hook,
                "%s (%d MB)" % (target.name, size // (1024 * 1024)))
            continue
        text = read_text(target)
        if text is None:
            continue
        src, sink = SECRET_SOURCES.search(text), EXFIL_SINKS.search(text)
        if src and sink:
            add("HIGH", "hook-exfil", loc,
                "Install hook '%s' reads credentials and sends data out" % hook,
                "%s ... %s" % (_snippet(text, src), _snippet(text, sink)))
        blob = OBFUSCATED_BLOB.search(text)
        if blob and DYNAMIC_EVAL.search(text):
            add("MEDIUM", "hook-obfuscated", loc, "Install hook '%s' runs heavily obfuscated code" % hook,
                "%d-char encoded blob + dynamic eval" % len(blob.group(0)))
        dl = RUNTIME_DOWNLOAD.search(text)
        if dl:
            add("MEDIUM", "hook-runtime-download", loc,
                "Install hook '%s' downloads a runtime or secret scanner" % hook, _snippet(text, dl))
    return out
