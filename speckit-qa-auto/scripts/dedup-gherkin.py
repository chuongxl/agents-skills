#!/usr/bin/env python3
"""Deduplicate candidate Gherkin scenarios against existing feature files."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

SCENARIO_RE = re.compile(r"^\s*Scenario(?: Outline)?:\s*(.+?)\s*$", re.I)
STEP_RE = re.compile(r"^\s*(Given|When|Then|And|But)\s+(.+?)\s*$", re.I)
TOKEN_RE = re.compile(r"[a-z0-9]+")


@dataclass(frozen=True)
class Scenario:
    title: str
    steps: tuple[str, ...]
    source: str

    @property
    def title_key(self) -> str:
        return normalize(self.title)

    @property
    def full_key(self) -> str:
        return "\n".join((self.title_key, *self.steps))


def normalize(text: str) -> str:
    return " ".join(TOKEN_RE.findall(text.lower()))


def parse_feature(path: Path) -> list[Scenario]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise SystemExit(f"cannot read {path}: {exc}") from exc

    scenarios: list[Scenario] = []
    title: str | None = None
    steps: list[str] = []

    def flush() -> None:
        nonlocal title, steps
        if title is not None:
            scenarios.append(Scenario(title=title, steps=tuple(steps), source=str(path)))
        title = None
        steps = []

    for line in lines:
        scenario = SCENARIO_RE.match(line)
        if scenario:
            flush()
            title = scenario.group(1).strip()
            continue
        if title is None:
            continue
        step = STEP_RE.match(line)
        if step:
            steps.append(normalize(f"{step.group(1)} {step.group(2)}"))

    flush()
    return scenarios


def dedup(existing_paths: list[Path], candidate_path: Path) -> dict[str, object]:
    existing: list[Scenario] = []
    for path in existing_paths:
        existing.extend(parse_feature(path))
    candidates = parse_feature(candidate_path)

    by_full = {scenario.full_key: scenario for scenario in existing}
    by_title = {scenario.title_key: scenario for scenario in existing}

    results: list[dict[str, str]] = []
    for scenario in candidates:
        if scenario.full_key in by_full:
            match = by_full[scenario.full_key]
            results.append(
                {
                    "scenario": scenario.title,
                    "label": "SKIP",
                    "reason": "same normalized title and steps already exist",
                    "matched_existing": match.source,
                }
            )
        elif scenario.title_key in by_title:
            match = by_title[scenario.title_key]
            results.append(
                {
                    "scenario": scenario.title,
                    "label": "REVIEW",
                    "reason": "same normalized title exists with different steps",
                    "matched_existing": match.source,
                }
            )
        else:
            results.append(
                {
                    "scenario": scenario.title,
                    "label": "NEW",
                    "reason": "no normalized scenario match found",
                    "matched_existing": "",
                }
            )

    return {
        "existing_count": len(existing),
        "candidate_count": len(candidates),
        "scenarios": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--existing", action="append", required=True, type=Path)
    parser.add_argument("--candidate", required=True, type=Path)
    args = parser.parse_args()

    print(json.dumps(dedup(args.existing, args.candidate), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
