#!/usr/bin/env python3
"""Validate the speckit-qa-auto run.json artifact contract."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ISSUE_RE = re.compile(r"^[A-Z][A-Z0-9]+-\d+$")
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")

STAGES = {
    "intake",
    "discovered",
    "brainstorming",
    "brainstorm-approved",
    "design-drafting",
    "design-approved",
    "reviewing",
    "review-passed",
    "automation",
    "automation-complete",
    "finished",
    "blocked",
}
RESUME_TARGETS = {None, "intake", "brainstorm", "design", "review", "automation", "finish", "done"}
COVERAGE_VALUES = {
    "dedup": {"not-run", "ran", "skipped"},
    "xray": {"available", "unavailable", "not-configured"},
}
DESIGN_REQUIRED_STAGES = {
    "design-approved",
    "reviewing",
    "review-passed",
    "automation",
    "automation-complete",
    "finished",
}
BRAINSTORM_REQUIRED_STAGES = {
    "brainstorm-approved",
    "design-drafting",
    "design-approved",
    "reviewing",
    "review-passed",
    "automation",
    "automation-complete",
    "finished",
}
BRAINSTORM_STATUSES = {"pending", "approved"}
REVIEW_REQUIRED_STAGES = {
    "review-passed",
    "automation",
    "automation-complete",
    "finished",
}
REVIEW_STATUSES = {"pending", "passed", "changes-requested"}


def _workspace_root(run_dir: Path) -> Path:
    parts = run_dir.resolve().parts
    for idx in range(len(parts) - 2):
        if parts[idx] == "docs" and parts[idx + 1] == "qa":
            return Path(*parts[:idx]) if idx else Path("/")
    return run_dir.resolve()


def _artifact_path(raw: str, workspace: Path) -> Path:
    path = Path(raw)
    if not path.is_absolute():
        path = workspace / path
    return path.resolve()


def _require_object(value: Any, field: str, errors: list[str]) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    errors.append(f"{field} must be an object")
    return {}


def validate(path: Path) -> list[str]:
    errors: list[str] = []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        return [f"cannot read {path}: {exc}"]
    except json.JSONDecodeError as exc:
        return [f"invalid JSON: {exc}"]

    if not isinstance(data, dict):
        return ["run.json must contain a JSON object"]

    issue = data.get("issue")
    if not isinstance(issue, str) or not ISSUE_RE.match(issue):
        errors.append("issue must be a Jira key like MOM-1234")

    stage = data.get("stage")
    if stage not in STAGES:
        errors.append(f"stage must be one of {', '.join(sorted(STAGES))}")

    resume_target = data.get("resume_target")
    if resume_target not in RESUME_TARGETS:
        errors.append("resume_target must be intake, brainstorm, design, review, automation, finish, done, or null")

    adapter = data.get("adapter")
    if adapter is not None and (not isinstance(adapter, str) or not SLUG_RE.match(adapter)):
        errors.append("adapter must be null or a lowercase kebab-case adapter id")

    brainstorm = _require_object(data.get("brainstorm"), "brainstorm", errors)
    brainstorm_status = brainstorm.get("status")
    if brainstorm_status not in BRAINSTORM_STATUSES:
        errors.append("brainstorm.status must be pending or approved")
    brainstorm_required = (
        stage in BRAINSTORM_REQUIRED_STAGES
        or resume_target in {"design", "review", "automation", "finish", "done"}
    )
    if brainstorm_required and brainstorm_status != "approved":
        errors.append("brainstorm.status must be approved before design, review, automation, finish, or done")
    if brainstorm_status == "approved":
        approach = brainstorm.get("approach")
        if not isinstance(approach, str) or not approach.strip():
            errors.append("brainstorm.approach must be a non-empty string when approved")
    for field in ("questions", "confirmed_assumptions", "rejected_approaches"):
        if not isinstance(brainstorm.get(field), list):
            errors.append(f"brainstorm.{field} must be a list")

    review = _require_object(data.get("review"), "review", errors)
    review_status = review.get("status")
    if review_status not in REVIEW_STATUSES:
        errors.append("review.status must be pending, passed, or changes-requested")
    review_required = (
        stage in REVIEW_REQUIRED_STAGES
        or resume_target in {"automation", "finish", "done"}
    )
    if review_required and review_status != "passed":
        errors.append("review.status must be passed before automation, finish, or done")
    if review_status == "changes-requested" and resume_target not in {"design", "review"}:
        errors.append("review.status changes-requested must route back to design or review")
    for field in ("findings", "decisions"):
        if not isinstance(review.get(field), list):
            errors.append(f"review.{field} must be a list")

    run_dir = path.resolve().parent
    workspace = _workspace_root(run_dir)
    artifacts = _require_object(data.get("artifacts"), "artifacts", errors)
    design_required = (
        stage in DESIGN_REQUIRED_STAGES
        or resume_target in {"review", "automation", "finish", "done"}
    )

    feature_files = artifacts.get("feature_files")
    if not isinstance(feature_files, list):
        errors.append("artifacts.feature_files must be a list")
    elif design_required and not feature_files:
        errors.append("artifacts.feature_files must be non-empty after design approval")
    else:
        for raw in feature_files:
            if not isinstance(raw, str):
                errors.append("artifacts.feature_files entries must be strings")
                continue
            resolved = _artifact_path(raw, workspace)
            if not resolved.is_relative_to(run_dir):
                errors.append(f"feature file escapes run folder: {raw}")
            elif not resolved.is_file():
                errors.append(f"feature file does not exist: {raw}")

    test_design = artifacts.get("test_design")
    if test_design is None and not design_required:
        pass
    elif not isinstance(test_design, str):
        errors.append("artifacts.test_design must be a string path")
    else:
        resolved = _artifact_path(test_design, workspace)
        if not resolved.is_relative_to(run_dir):
            errors.append(f"test_design escapes run folder: {test_design}")
        elif not resolved.is_file():
            errors.append(f"test_design does not exist: {test_design}")

    coverage = _require_object(data.get("coverage"), "coverage", errors)
    for field, values in COVERAGE_VALUES.items():
        value = coverage.get(field)
        if value not in values:
            errors.append(f"coverage.{field} must be one of {', '.join(sorted(values))}")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_json", type=Path, help="Path to docs/qa/<issue>/run.json")
    args = parser.parse_args()

    errors = validate(args.run_json)
    if errors:
        print("run.json invalid:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1
    print(json.dumps({"ok": True, "path": str(args.run_json)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
