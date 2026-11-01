"""inventory.py - build the component inventory that advisories are matched against.

Stdlib only; Python 3.8+.

Sources: a CycloneDX SBOM (packages, by purl), runtime versions read with the
'runtime.extractors' of the ecosystem descriptors, and an explicit JSON inventory.
"""

import json
import os
import re

import advisory as adv_lib
import versions
import ecosystems
from component import Component, PurlError, parse_purl, canonical_purl


def from_cyclonedx(path):
    data = adv_lib.load_json(path)
    comps = []
    for c in data.get("components", []):
        purl = c.get("purl")
        if not purl:
            continue
        try:
            p = parse_purl(purl)
        except PurlError:
            continue
        name = "/".join(x for x in (p["namespace"], p["name"]) if x) if p["type"] in ("golang", "npm") else (
            "%s:%s" % (p["namespace"], p["name"]) if p["namespace"] and p["type"] == "maven" else p["name"])
        comps.append(Component("package", p["type"], name, p["version"], canonical_purl(purl),
                               location=c.get("name"), extra={"exact": True}))
    return comps


def from_json(path):
    data = adv_lib.load_json(path)
    comps = []
    for c in data.get("components", []):
        comps.append(Component(c["kind"], c["ecosystem"], c["name"], c.get("version"), c.get("purl"),
                               c.get("location"), {"exact": c.get("exact", True)}))
    return comps


def _is_exact(version):
    return bool(re.fullmatch(r"v?\d+\.\d+\.\d+([-+.]\S*)?", version or ""))


def runtimes_from_repo(repo, descriptors=None):
    """Read declared runtime versions of every detected ecosystem (best effort).

    Declared versions are often partial ('22') or ranges; those are marked exact=False so
    the matcher reports 'possibly-affected' rather than a firm hit.
    """
    descriptors = descriptors or ecosystems.load_descriptors()
    det = ecosystems.detect(repo, descriptors)
    by_id = {d["id"]: d for d in descriptors}
    found, seen = [], set()
    for eco in det["ecosystems"]:
        rt = by_id[eco["id"]].get("runtime")
        if not rt:
            continue
        dirs = sorted({os.path.dirname(m) for m in eco["manifests"]} | {""})
        for ex in rt.get("extractors", []):
            for d in dirs:
                f = os.path.join(repo, d, ex["file"])
                if not os.path.isfile(f):
                    continue
                v = _normalize_version(_extract(f, ex))
                if v and (rt["name"], v, d) not in seen:
                    seen.add((rt["name"], v, d))
                    found.append(Component("runtime", rt["name"], rt["name"], v, None,
                                           os.path.join(d, ex["file"]) if d else ex["file"],
                                           {"exact": _is_exact(v)}))
    return found


def _normalize_version(v):
    """Keep only concrete versions ('22', 'v22.14.0'); ranges ('>=22', '^20') and aliases ('lts/*') are dropped."""
    v = (v or "").strip()
    return v.lstrip("vV") if versions.parse(v) is not None else None


def _extract(path, ex):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            text = fh.read()
    except OSError:
        return None
    if "regex" in ex:
        m = re.search(ex["regex"], text, re.MULTILINE)
        return m.group(1) if m else None
    try:
        node = json.loads(text)
    except ValueError:
        return None
    for part in ex["json_path"].split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node if isinstance(node, str) else None


def facts_from_repo(repo):
    """Environment facts inferred from Dockerfiles: os and libc of the base image."""
    facts = {}
    for dirpath, dirnames, files in os.walk(repo):
        dirnames[:] = [d for d in dirnames if d not in ecosystems.SKIP_DIRS]
        for f in files:
            if f == "Dockerfile" or f.startswith("Dockerfile."):
                try:
                    text = open(os.path.join(dirpath, f), encoding="utf-8", errors="replace").read()
                except OSError:
                    continue
                for m in re.finditer(r"^\s*FROM\s+(?:--platform=\S+\s+)?(\S+)", text, re.MULTILINE | re.IGNORECASE):
                    image = m.group(1).lower()
                    if image == "scratch":
                        continue
                    facts["os"] = "linux"
                    if "alpine" in image or "musl" in image:
                        facts["libc"] = "musl"
                    elif "distroless" in image or any(k in image for k in ("debian", "ubuntu", "bookworm", "bullseye", "slim", "node:", "python:", "eclipse-temurin")):
                        facts.setdefault("libc", "glibc")
    return facts
