"""runtimes.py - declared runtime versions from Dockerfiles, compose files and CI workflows.

Stdlib only; Python 3.8+.

Complements the per-ecosystem 'runtime.extractors' (inventory.runtimes_from_repo): those read
version files such as .nvmrc, this reads the places a runtime is chosen by image tag or CI action.
A tag that names no concrete version ('latest', 'lts-alpine') is a floating declaration: the
component has version None and extra['floating'] = True, so it can be reported as 'cannot prove patched'.
"""

import glob
import os
import re

import ecosystems
from component import Component

# image name (last path segment) -> runtime name used by the ecosystem descriptors
IMAGE_RUNTIMES = {
    "node": "node", "python": "python", "golang": "go", "openjdk": "java",
    "eclipse-temurin": "java", "amazoncorretto": "java", "ruby": "ruby", "php": "php",
}
CI_ACTIONS = {"node-version": "node", "python-version": "python", "go-version": "go",
              "java-version": "java", "dotnet-version": "dotnet"}

_FROM_RE = re.compile(r"^\s*FROM\s+(?:--\S+\s+)*(\S+)(?:\s+AS\s+(\S+))?", re.IGNORECASE)
_ARG_RE = re.compile(r"^\s*ARG\s+(\w+)(?:=(\S+))?", re.IGNORECASE)
_VAR_RE = re.compile(r"\$\{(\w+)(?:[:-]+([^}]*))?\}|\$(\w+)")
_TAG_VER_RE = re.compile(r"^v?(\d+(?:\.\d+)*)(?:[-_+].*)?$")
_DOCKER_FILES = ("Dockerfile", "Containerfile")


def runtime_of_image(image):
    """('node', '22.14.0'|'22'|None) for 'node:22.14.0-alpine'; None when the image is not a known runtime."""
    ref = image.split("@")[0]
    name, _, tag = ref.rpartition(":") if ":" in ref.rsplit("/", 1)[-1] else (ref, "", "")
    base = name.lower().rsplit("/", 1)[-1]
    if "dotnet/" in name.lower():
        rt = "dotnet"
    else:
        rt = IMAGE_RUNTIMES.get(base)
    if rt is None:
        return None
    m = _TAG_VER_RE.match(tag)
    return rt, (m.group(1) if m else None)


def _declared(runtime, version, location, declared):
    floating = version is None
    exact = bool(version and re.fullmatch(r"\d+\.\d+\.\d+", version))
    return Component("runtime", runtime, runtime, version, None, location,
                     {"exact": exact, "floating": floating, "declared": declared})


def _subst(text, args):
    def sub(m):
        name = m.group(1) or m.group(3)
        return args.get(name, m.group(2) or "")
    return _VAR_RE.sub(sub, text)


def from_dockerfile(path, location):
    """Runtime of the final build stage (follows 'FROM <earlier stage>'). Build stages are not the shipped runtime."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            lines = fh.read().splitlines()
    except OSError:
        return []
    args, stages, last = {}, {}, None
    for line in lines:
        m = _ARG_RE.match(line)
        if m and last is None:      # only ARGs before the first FROM are visible in FROM lines
            args[m.group(1)] = m.group(2) or ""
            continue
        m = _FROM_RE.match(line)
        if not m:
            continue
        image = _subst(m.group(1), args)
        while image.lower() in stages:
            image = stages[image.lower()]
        if m.group(2):
            stages[m.group(2).lower()] = image
        last = image
    if not last or last.lower() == "scratch":
        return []
    r = runtime_of_image(last)
    return [_declared(r[0], r[1], location, last)] if r else []


def from_compose(path, location):
    out = []
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            text = fh.read()
    except OSError:
        return out
    for m in re.finditer(r"^\s*image:\s*['\"]?([^\s'\"#]+)", text, re.MULTILINE):
        r = runtime_of_image(m.group(1))
        if r:
            out.append(_declared(r[0], r[1], location, m.group(1)))
    return out


def from_workflow(path, location):
    out = []
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            text = fh.read()
    except OSError:
        return out
    for m in re.finditer(r"^\s*(%s):\s*['\"]?([^\s'\"#]+)" % "|".join(CI_ACTIONS), text, re.MULTILINE):
        raw = m.group(2)
        v = re.match(r"^v?(\d+(?:\.\d+)*)(?:\.x)?$", raw)    # '22', '22.14.0', '22.x'; matrix refs and 'lts/*' are floating
        out.append(_declared(CI_ACTIONS[m.group(1)], v.group(1) if v else None, location, raw))
    return out


def from_repo(repo):
    """Components declared in Dockerfiles, docker-compose files and GitHub workflows of the repo."""
    comps = []
    for dirpath, dirnames, files in os.walk(repo):
        dirnames[:] = sorted(d for d in dirnames if d not in ecosystems.SKIP_DIRS)
        for f in sorted(files):
            p = os.path.join(dirpath, f)
            rel = os.path.relpath(p, repo)
            if f in _DOCKER_FILES or f.startswith(tuple(x + "." for x in _DOCKER_FILES)):
                comps += from_dockerfile(p, rel)
            elif re.fullmatch(r"(docker-)?compose(\.[\w-]+)?\.ya?ml", f):
                comps += from_compose(p, rel)
    for p in sorted(glob.glob(os.path.join(repo, ".github", "workflows", "*.y*ml"))):
        comps += from_workflow(p, os.path.relpath(p, repo))
    return comps
