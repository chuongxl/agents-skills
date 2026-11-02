"""Host ("laptop") mode: projects under the given roots, global installs, package caches,
and an inventory of credential stores to rotate if the machine turns out to be affected.

Never runs npm/node/pip. Credential files are never read into findings; only ~/.npmrc is read,
to answer "has auth token: yes|no".
"""

import glob
import json
import os
import re
import stat
from pathlib import Path

from .findings import make_finding, relocate
from .inventory import NPM_LOCKS, prune
from .scanner import scan_repo

PROJECT_MARKERS = set(NPM_LOCKS) | {"package.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock", "uv.lock",
                                    "pdm.lock", "node_modules"}
SKIP_DIRS = {".git", ".hg", ".svn", "node_modules", "Library", ".Trash", ".cache", ".npm", ".bun", ".nvm",
             ".cargo", ".rustup", ".gradle", ".m2", ".pyenv", ".vscode-server", "AppData", "snap",
             "site-packages", "__pycache__", "proc", "sys", "dev"}
_TARBALL = re.compile(r"registry\.npmjs\.org/((?:@[^/\"\s]+(?:/|%2[fF]))?[^/\"\s]+)/-/[^/\"\s]+?-(\d[^/\"\s]*?)\.tgz")
_NPMRC_AUTH = re.compile(r"(_authToken|_auth|_password)\s*=", re.I)

CREDENTIAL_FILES = [  # (path relative to home, private?)
    (".npmrc", True), (".git-credentials", True), (".config/gh/hosts.yml", True),
    (".aws/credentials", True), (".aws/config", False), (".azure", True),
    (".config/gcloud/application_default_credentials.json", True), (".config/gcloud/credentials.db", True),
    (".docker/config.json", True), (".kube/config", True), (".terraform.d/credentials.tfrc.json", True),
]


def _display(path, home):
    path, home = os.path.abspath(str(path)), os.path.abspath(str(home))
    if path == home:
        return "~"
    if path.startswith(home + os.sep):
        return "~/" + os.path.relpath(path, home).replace(os.sep, "/")
    return path.replace(os.sep, "/")


def _is_project(dirpath, names):
    return bool(PROJECT_MARKERS & set(names)) or any(n.startswith("requirements") and n.endswith(".txt") for n in names)


def find_projects(root, home, max_depth):
    """Directories under root that hold a project (lockfile, manifest or node_modules), depth-limited.
    A project is not descended into further (scan_repo covers its subtree). $HOME itself is never a project."""
    root = os.path.abspath(str(root))
    home = os.path.abspath(str(home))
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        depth = 0 if dirpath == root else os.path.relpath(dirpath, root).count(os.sep) + 1
        names = filenames + dirnames
        if dirpath != home and _is_project(dirpath, names):
            yield Path(dirpath)
            dirnames[:] = []
            continue
        prune(dirpath, dirnames, skip=SKIP_DIRS)
        dirnames[:] = [d for d in dirnames if depth < max_depth and not os.path.islink(os.path.join(dirpath, d))]


def _env_files(project):
    for p in sorted(Path(project).glob(".env*")):
        if p.is_file() and not p.is_symlink() and not p.name.endswith((".example", ".sample", ".template")):
            yield p


def global_module_dirs(home):
    prefixes = []
    if os.environ.get("NPM_CONFIG_PREFIX"):
        prefixes.append(os.environ["NPM_CONFIG_PREFIX"])
    npmrc = home / ".npmrc"
    try:
        for line in npmrc.read_text(errors="replace").splitlines():
            if line.strip().startswith("prefix") and "=" in line:
                prefixes.append(os.path.expanduser(line.split("=", 1)[1].strip()))
    except OSError:
        pass
    prefixes += [str(home / ".npm-global"), "/usr/local", "/opt/homebrew", "/usr"]
    dirs = []
    for pre in prefixes:
        dirs += [os.path.join(pre, "lib", "node_modules"), os.path.join(pre, "node_modules")]
    dirs += glob.glob(str(home / ".nvm" / "versions" / "node" / "*" / "lib" / "node_modules"))
    dirs += [str(home / ".bun" / "install" / "global" / "node_modules"),
             str(home / ".local" / "share" / "pnpm" / "global"),
             str(home / ".config" / "yarn" / "global" / "node_modules")]
    seen, out = set(), []
    for d in dirs:
        real = os.path.realpath(d)
        if real not in seen and os.path.isdir(real):
            seen.add(real)
            out.append(Path(d))
    return out


def _package_dirs(modules_dir):
    for child in sorted(Path(modules_dir).iterdir()):
        if child.is_symlink() or not child.is_dir() or child.name.startswith("."):
            continue
        if child.name.startswith("@"):
            for sub in sorted(child.iterdir()):
                if sub.is_dir() and not sub.is_symlink():
                    yield sub
        else:
            yield child


def scan_global_modules(home, ioc, allowlist):
    """Each globally installed package: its own release, its files and hooks, and its dependencies."""
    out = []
    for nm in global_module_dirs(home):
        try:
            pkg_dirs = list(_package_dirs(nm))
        except OSError:
            continue
        for pkg_dir in pkg_dirs:
            shown = _display(pkg_dir, home)
            try:
                manifest = json.loads((pkg_dir / "package.json").read_text(encoding="utf-8"))
            except (OSError, ValueError):
                manifest = {}
            name, version = manifest.get("name"), manifest.get("version")
            wave = ioc.package_wave("npm", name, version) if isinstance(name, str) and isinstance(version, str) else None
            if wave:
                out.append(make_finding("affected", "CRITICAL", "known-package", shown + "/package.json",
                                        "Known compromised npm release installed globally",
                                        package=name, version=version, wave=wave))
            out.extend(relocate(f, shown) for f in scan_repo(pkg_dir, ioc, allowlist))
    return out


def scan_site_packages(home, ioc):
    out = []
    for meta in glob.glob(str(home / ".local" / "lib" / "python3*" / "site-packages" / "*.dist-info" / "METADATA")):
        name = version = None
        try:
            with open(meta, "r", encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    if line.startswith("Name:"):
                        name = line[5:].strip()
                    elif line.startswith("Version:"):
                        version = line[8:].strip()
                    elif not line.strip():
                        break
        except OSError:
            continue
        wave = ioc.package_wave("pypi", name, version) if name and version else None
        if wave:
            from .iocs import normalize_name
            out.append(make_finding("affected", "CRITICAL", "known-package", _display(meta, home),
                                    "Known compromised pypi release installed for this user",
                                    package=normalize_name("pypi", name), version=version, wave=wave))
    return out


def scan_npm_cache(home, ioc):
    cache = Path(os.environ.get("npm_config_cache") or (home / ".npm")) / "_cacache" / "index-v5"
    out = []
    if not cache.is_dir():
        return out
    for dirpath, _dirs, files in os.walk(str(cache), followlinks=False):
        for fn in files:
            try:
                with open(os.path.join(dirpath, fn), "r", encoding="utf-8", errors="replace") as fh:
                    text = fh.read(1 << 20)
            except OSError:
                continue
            for m in _TARBALL.finditer(text):
                name, version = m.group(1).replace("%2f", "/").replace("%2F", "/"), m.group(2)
                wave = ioc.package_wave("npm", name, version)
                if wave:
                    out.append(make_finding("affected", "CRITICAL", "cached-package", _display(cache.parent, home),
                                            "Known compromised npm release in the npm cache",
                                            package=name, version=version, wave=wave))
    return out


def _too_open(path):
    if os.name == "nt":
        return False
    try:
        return bool(os.stat(str(path)).st_mode & 0o077)
    except OSError:
        return False


def credential_inventory(home, projects):
    out = []
    entries = [(home / rel, private) for rel, private in CREDENTIAL_FILES]
    ssh = home / ".ssh"
    if ssh.is_dir():
        entries += [(p, True) for p in sorted(ssh.glob("id_*")) if not p.name.endswith(".pub")]
    for path, private in entries:
        if not path.exists() or path.is_symlink():
            continue
        loc = _display(path, home)
        evidence = "present"
        if path.name == ".npmrc" and path.parent == home:
            try:
                evidence = "has auth token: %s" % ("yes" if _NPMRC_AUTH.search(path.read_text(errors="replace")) else "no")
            except OSError:
                evidence = "present (unreadable)"
        out.append(make_finding("exposure", "INFO", "credential-store", loc,
                                "Credential store to rotate if this machine is affected", evidence=evidence))
        if private and path.is_file() and _too_open(path):
            out.append(make_finding("exposure", "MEDIUM", "credential-permissions", loc,
                                    "Credential file readable by other users",
                                    evidence="mode %o" % stat.S_IMODE(os.stat(str(path)).st_mode)))
    for project in projects:
        for env in _env_files(project):
            out.append(make_finding("exposure", "INFO", "credential-store", _display(env, home),
                                    "Project secrets file to rotate if this machine is affected", evidence="present"))
    return out


def scan_host(roots, home, ioc, allowlist, max_depth=8):
    home = Path(home)
    out, projects = [], []
    for root in roots:
        for project in find_projects(root, home, max_depth):
            projects.append(project)
            out.extend(relocate(f, _display(project, home)) for f in scan_repo(project, ioc, allowlist))
    # persistence files the worm drops in the home directory itself (.claude/, .vscode/)
    from .scanner import check_paths
    out.extend(relocate(f, "~") for f in check_paths(home, ioc))
    out.extend(scan_global_modules(home, ioc, allowlist))
    out.extend(scan_site_packages(home, ioc))
    out.extend(scan_npm_cache(home, ioc))
    out.extend(credential_inventory(home, projects))
    return out
