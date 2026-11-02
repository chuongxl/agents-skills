#!/usr/bin/env python3
"""probe-runtime.py - ask the final image of each Dockerfile which runtime version it really ships.

Usage:
  python3 -I scripts/probe-runtime.py --repo DIR --output inventory.json [--timeout 300]

A tag such as node:22-alpine says nothing about the patch level, and official Node images carry a
tarball binary that package scanners can miss, so the version the image reports ('node -v') is the
source of truth. Writes a match.py --inventory file with exact runtime components. Without a
working docker the probe is skipped (exit 0, nothing written) and says so on stderr: skipped, not clean.

Only the base image named in the Dockerfile is run, with --entrypoint set to the runtime binary and
no network, so nothing from the repository executes. Stdlib only; Python 3.8+. Run with -I.
"""

import argparse
import json
import os
import re
import subprocess
import sys

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(SKILL_DIR, "scripts", "lib"))

import ecosystems  # noqa: E402
import runtimes  # noqa: E402

PROBES = {"node": ("node", ["-v"]), "python": ("python", ["-V"]), "go": ("go", ["version"]),
          "java": ("java", ["-version"])}
_IMAGE_RE = re.compile(r"[A-Za-z0-9][\w./:@-]*")
_VER_RE = re.compile(r"(\d+\.\d+\.\d+)")


def parse_version(runtime, text):
    """'v22.14.0' / 'Python 3.12.1' / 'go version go1.22.3 linux/amd64' / 'openjdk version "17.0.9"' -> '22.14.0' ..."""
    if runtime == "go":
        text = text.replace("go1", "1")
    m = _VER_RE.search(text)
    return m.group(1) if m else None


def probe(runtime, image, timeout):
    binary, args = PROBES[runtime]
    r = subprocess.run(["docker", "run", "--rm", "--network", "none", "--entrypoint", binary, image] + args,
                       capture_output=True, text=True, timeout=timeout)
    return parse_version(runtime, r.stdout + r.stderr) if r.returncode == 0 else None


def main(argv=None):
    ap = argparse.ArgumentParser(description="Probe runtime versions inside Dockerfile base images")
    ap.add_argument("--repo", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--timeout", type=int, default=300)
    args = ap.parse_args(argv)

    images = {}
    for c in runtimes.from_repo(args.repo):
        image = c.extra.get("declared")
        if c.location and os.path.basename(c.location).startswith(("Dockerfile", "Containerfile")) and c.name in PROBES \
                and image and _IMAGE_RE.fullmatch(image):
            images[(c.name, image)] = c.location
    if not images:
        print("probe: no Dockerfile with a probe-able runtime image", file=sys.stderr)
        return 0
    try:
        subprocess.run(["docker", "version"], capture_output=True, timeout=30, check=True)
    except (OSError, subprocess.SubprocessError):
        print("probe: SKIPPED - docker is not available; declared tags are not verified", file=sys.stderr)
        return 0

    comps = []
    for (runtime, image), location in sorted(images.items()):
        try:
            v = probe(runtime, image, args.timeout)
        except (OSError, subprocess.SubprocessError) as exc:
            print("probe: %s failed: %s" % (image, exc), file=sys.stderr)
            continue
        if not v:
            print("probe: %s did not report a version" % image, file=sys.stderr)
            continue
        print("probe: %s -> %s %s" % (image, runtime, v), file=sys.stderr)
        comps.append({"kind": "runtime", "ecosystem": runtime, "name": runtime, "version": v,
                      "location": "%s (image %s)" % (location, image), "exact": True})
    if comps:
        os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as fh:
            json.dump({"components": comps}, fh, indent=2)
            fh.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
