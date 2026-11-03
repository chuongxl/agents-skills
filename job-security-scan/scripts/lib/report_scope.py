"""Scope a report to the files changed since a git ref (run-scan.sh --since).

run-scan.sh writes {repo folder: [changed paths relative to the repo]} or {repo folder: null} when the repo
could not be scoped (not a git repo, unknown ref) — those repos keep every finding.
A finding stays when its file changed; a dependency finding without a file stays when any lockfile or manifest of
its repo changed; host findings (this machine) and findings with no file always stay, so nothing is hidden that
the scope cannot judge. Stdlib only; Python 3.8+.
"""

import json
import os

import report_locate

HOST_LABEL = "this machine"
MAX_BYTES = 5 * 1024 * 1024


def load_changed(path):
    if os.path.getsize(path) > MAX_BYTES:
        raise ValueError("%s is larger than %d bytes" % (path, MAX_BYTES))
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise ValueError("changed-files must map repo -> list of paths")
    out = {}
    for repo, files in data.items():
        out[str(repo)] = None if files is None else set(_norm(f) for f in files if isinstance(f, str))
    return out


def _norm(path):
    if not path:
        return ""
    p = os.path.normpath(str(path).replace("\\", "/"))
    return "" if p == "." else p


def _is_dependency_file(path):
    return report_locate.is_dependency_file(os.path.basename(path))


def filter_changed(findings, changed):
    kept = []
    for f in findings:
        repo = f.get("repo")
        files = changed.get(repo)
        if repo == HOST_LABEL or repo not in changed or files is None:
            kept.append(f)
            continue
        path = _norm(f.get("file"))
        if not path:
            if f.get("package") and any(_is_dependency_file(c) for c in files):
                kept.append(f)
            elif not f.get("package"):
                kept.append(f)
            continue
        if path in files or any(path.endswith("/" + c) for c in files):
            kept.append(f)
    return kept
