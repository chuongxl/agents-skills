"""Repo mode: known-indicator (tier 1) checks, plus the tier-2 heuristics per package manifest."""

import hashlib
import os
from pathlib import Path

from . import MAX_SCAN_BYTES
from .findings import make_finding
from .heuristics import analyze_manifest
from .hooks import hook_targets, install_hooks, read_text
from .inventory import iter_manifests, iter_packages, prune

PAYLOAD_DEPTH = 2
WORKFLOW_DIR = Path(".github") / "workflows"


def _rel(root, path):
    return os.path.relpath(str(path), str(root)).replace(os.sep, "/")


def _sha256(path):
    try:
        if os.path.getsize(str(path)) > MAX_SCAN_BYTES:
            return None
        h = hashlib.sha256()
        with open(str(path), "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def _files_near(pkg_dir, depth=PAYLOAD_DEPTH):
    """Files in pkg_dir up to `depth` levels, not entering nested node_modules or VCS dirs."""
    base = str(pkg_dir)
    for dirpath, dirnames, filenames in os.walk(base, followlinks=False):
        level = 0 if dirpath == base else os.path.relpath(dirpath, base).count(os.sep) + 1
        prune(dirpath, dirnames, skip={"node_modules", ".git"})
        if level >= depth:
            dirnames[:] = []
        for fn in filenames:
            yield Path(dirpath) / fn


def _payload_hit(ioc, path):
    spec = ioc.files.get(path.name)
    if not spec or path.is_symlink():
        return None
    if spec["sha256"]:
        return spec if _sha256(path) in spec["sha256"] else None
    return spec


def _markers_in(ioc, text):
    return [m for m in ioc.markers if m["text"] in text] if text else []


def _marker_findings(root, ioc, path, text):
    out = []
    for m in _markers_in(ioc, text):
        out.append(make_finding("affected", "CRITICAL", "marker", _rel(root, path),
                                "Shai-Hulud marker string found", wave=m["wave"], evidence=m["text"]))
    return out


def check_packages(root, ioc):
    out = []
    for pkg in iter_packages(root):
        wave = ioc.package_wave(pkg.ecosystem, pkg.name, pkg.version)
        if wave:
            out.append(make_finding("affected", "CRITICAL", "known-package", pkg.location,
                                    "Known compromised %s release" % pkg.ecosystem,
                                    package=pkg.name, version=pkg.version, wave=wave))
    return out


def check_manifest_files(root, ioc, pkg_dir, manifest):
    """Payload files inside a package dir, and markers/payloads referenced by its install hooks."""
    out = []
    name = manifest.get("name", "") if isinstance(manifest.get("name"), str) else ""
    version = manifest.get("version", "") if isinstance(manifest.get("version"), str) else ""
    for path in _files_near(pkg_dir):
        spec = _payload_hit(ioc, path)
        if spec:
            out.append(make_finding("affected", "CRITICAL", "payload-file", _rel(root, path),
                                    "Shai-Hulud %s file in package" % spec["kind"],
                                    package=name, version=version, wave=spec["wave"]))
    for hook, command in install_hooks(manifest):
        for target in hook_targets(pkg_dir, command):
            out.extend(_marker_findings(root, ioc, target, read_text(target)))
    return out


def check_paths(root, ioc):
    out = []
    for spec in ioc.paths:
        for path in sorted(root.glob(spec["pattern"])):
            if not path.is_file() or path.is_symlink():
                continue
            marker = spec.get("requires_marker")
            if marker and marker not in (read_text(path) or ""):
                continue
            out.append(make_finding("affected", "CRITICAL", "planted-path", _rel(root, path),
                                    "File planted by the Shai-Hulud worm", wave=spec["wave"],
                                    evidence=marker or spec["pattern"]))
    workflows = root / WORKFLOW_DIR
    if workflows.is_dir():
        for path in sorted(workflows.iterdir()):
            if path.is_file() and not path.is_symlink() and path.suffix in (".yml", ".yaml"):
                out.extend(_marker_findings(root, ioc, path, read_text(path)))
    for spec in ioc.paths:
        if spec["pattern"].startswith(str(WORKFLOW_DIR)):
            continue
        for path in root.glob(spec["pattern"]):
            if path.is_file() and not path.is_symlink():
                out.extend(_marker_findings(root, ioc, path, read_text(path)))
    return out


def scan_repo(root, ioc, allowlist):
    """All findings for one directory tree (a repo or a project found on the host)."""
    root = Path(root)
    out = check_packages(root, ioc) + check_paths(root, ioc)
    for pkg_dir, manifest in iter_manifests(root):
        out.extend(check_manifest_files(root, ioc, pkg_dir, manifest))
        out.extend(analyze_manifest(pkg_dir, manifest, allowlist, root, ioc))
    return out
