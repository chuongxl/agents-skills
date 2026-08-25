#!/usr/bin/env python3
"""Detect an optional speckit-qa-auto automation adapter for a repository."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def _read_package_json(repo: Path) -> dict[str, Any]:
    path = repo / "package.json"
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"invalid package.json: {exc}") from exc
    if not isinstance(payload, dict):
        return {}
    return payload


def _dependencies(package: dict[str, Any]) -> set[str]:
    names: set[str] = set()
    for field in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
        values = package.get(field, {})
        if isinstance(values, dict):
            names.update(str(name) for name in values)
    return names


def _scripts(package: dict[str, Any]) -> dict[str, str]:
    values = package.get("scripts", {})
    if not isinstance(values, dict):
        return {}
    return {str(k): str(v) for k, v in values.items()}


def detect(repo: Path) -> dict[str, Any]:
    package = _read_package_json(repo)
    deps = _dependencies(package)
    scripts = _scripts(package)
    evidence: list[str] = []

    if "playwright-bdd" in deps or any("bddgen" in command for command in scripts.values()):
        if "playwright-bdd" in deps:
            evidence.append("package.json dependency playwright-bdd")
        if "@playwright/test" in deps:
            evidence.append("package.json dependency @playwright/test")
        if any("bddgen" in command for command in scripts.values()):
            evidence.append("package.json script invokes bddgen")
        return {"adapter": "playwright-bdd", "confidence": "detected", "evidence": evidence}

    cypress_markers = {
        "@badeball/cypress-cucumber-preprocessor",
        "cypress-cucumber-preprocessor",
    }
    if deps & cypress_markers:
        evidence.extend(f"package.json dependency {name}" for name in sorted(deps & cypress_markers))
        if "cypress" in deps:
            evidence.append("package.json dependency cypress")
        return {"adapter": "cypress-cucumber", "confidence": "detected", "evidence": evidence}

    cucumber_markers = {"@cucumber/cucumber", "cucumber-js"}
    if deps & cucumber_markers:
        evidence.extend(f"package.json dependency {name}" for name in sorted(deps & cucumber_markers))
        return {"adapter": "cucumber-js", "confidence": "detected", "evidence": evidence}

    return {"adapter": None, "confidence": "none", "evidence": []}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repo", nargs="?", type=Path, default=Path.cwd())
    args = parser.parse_args()

    repo = args.repo.resolve()
    if not repo.is_dir():
        print(f"not a directory: {repo}", file=sys.stderr)
        return 2
    print(json.dumps(detect(repo), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
