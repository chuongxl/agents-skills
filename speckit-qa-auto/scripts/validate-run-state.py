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

STAGES = {
    "intake",
    "discovered",
    "impact-analysis",
    "brainstorming",
    "brainstorm-approved",
    "design-drafting",
    "design-approved",
    "reviewing",
    "review-passed",
    "automation",
    "automation-reviewing",
    "automation-complete",
    "finished",
    "blocked",
}
RESUME_TARGETS = {
    None,
    "intake",
    "impact",
    "brainstorm",
    "design",
    "review",
    "automation",
    "automation-review",
    "finish",
    "done",
}
COVERAGE_VALUES = {
    "dedup": {"not-run", "ran", "skipped"},
    "xray": {"available", "unavailable", "not-configured"},
}
IMPACT_REASONS = {"ok", "no-source-access", "entity-unresolved", "not-run"}
IMPACT_SOURCES = {"sweep", "declared", "both"}
CONVERSION_STATUSES = {"not-run", "pending", "approved"}
CONVERSION_MODES = {"link", "overwrite"}
IMPACT_RESOLVED_STAGES = {
    "brainstorming",
    "brainstorm-approved",
    "design-drafting",
    "design-approved",
    "reviewing",
    "review-passed",
    "automation",
    "automation-reviewing",
    "automation-complete",
    "finished",
}
AUTOMATION_STATUSES = {
    "not-requested",
    "pending",
    "deferred",
    "implemented",
    "review-passed",
    "blocked",
    "not-run",
}
AUTOMATION_REVIEW_STATUSES = {"not-run", "pending", "passed", "changes-requested"}
DESIGN_REQUIRED_STAGES = {
    "design-approved",
    "reviewing",
    "review-passed",
    "automation",
    "automation-reviewing",
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
    "automation-reviewing",
    "automation-complete",
    "finished",
}
BRAINSTORM_STATUSES = {"pending", "approved"}
REVIEW_REQUIRED_STAGES = {
    "review-passed",
    "automation",
    "automation-reviewing",
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
        errors.append(
            "resume_target must be intake, brainstorm, design, review, automation, automation-review, finish, done, or null"
        )

    if "adapter" in data:
        errors.append("adapter is not part of run.json; use automation.tool or automation.skill")

    automation = _require_object(data.get("automation"), "automation", errors)
    automation_status = automation.get("status")
    if automation_status not in AUTOMATION_STATUSES:
        errors.append(
            "automation.status must be one of " + ", ".join(sorted(AUTOMATION_STATUSES))
        )
    if not isinstance(automation.get("requested"), bool):
        errors.append("automation.requested must be a boolean")
    for field in ("tool", "skill", "result"):
        value = automation.get(field)
        if value is not None and not isinstance(value, str):
            errors.append(f"automation.{field} must be null or a string")
    automation_review = _require_object(automation.get("review"), "automation.review", errors)
    automation_review_status = automation_review.get("status")
    if automation_review_status not in AUTOMATION_REVIEW_STATUSES:
        errors.append("automation.review.status must be not-run, pending, passed, or changes-requested")
    if not isinstance(automation_review.get("findings"), list):
        errors.append("automation.review.findings must be a list")
    automation_finish_required = (
        stage in {"automation-complete", "finished"} or resume_target in {"finish", "done"}
    )
    if automation_status == "review-passed" and automation_review_status != "passed":
        errors.append("automation.review.status must be passed when automation status is review-passed")
    if automation_finish_required and automation_status == "implemented" and automation_review_status != "passed":
        errors.append("automation.review.status must be passed before finish when automation code is implemented")
    if automation_status == "review-passed" and not automation.get("result"):
        errors.append("automation.result must point to automation-result.json when automation is review-passed")

    deferred = automation.get("deferred")
    if automation_status == "deferred":
        if automation.get("requested") is not True:
            errors.append("automation.requested must be true when automation is deferred")
        if automation.get("result") is not None:
            errors.append("automation.result must be null when automation is deferred")
        if automation_review_status != "not-run":
            errors.append("automation.review.status must be not-run when automation is deferred")
        deferred_obj = _require_object(deferred, "automation.deferred", errors)
        for field in ("reason", "resume_when"):
            value = deferred_obj.get(field)
            if not isinstance(value, str) or not value.strip():
                errors.append(f"automation.deferred.{field} must be a non-empty string")
    elif deferred is not None:
        errors.append("automation.deferred is only valid when automation.status is deferred")

    brainstorm = _require_object(data.get("brainstorm"), "brainstorm", errors)
    brainstorm_status = brainstorm.get("status")
    if brainstorm_status not in BRAINSTORM_STATUSES:
        errors.append("brainstorm.status must be pending or approved")
    brainstorm_required = (
        stage in BRAINSTORM_REQUIRED_STAGES
        or resume_target in {"design", "review", "automation", "automation-review", "finish", "done"}
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

    impact = _require_object(data.get("impact"), "impact", errors)
    if not isinstance(impact.get("ran"), bool):
        errors.append("impact.ran must be a boolean")
    impact_reason = impact.get("reason")
    if impact_reason not in IMPACT_REASONS:
        errors.append(f"impact.reason must be one of {', '.join(sorted(IMPACT_REASONS))}")
    if impact.get("ran") is True and impact_reason != "ok":
        errors.append("impact.reason must be ok when impact.ran is true")
    if impact.get("ran") is False and impact_reason == "ok":
        errors.append("impact.reason ok requires impact.ran true")
    for field in ("entities", "declared", "candidates", "approved_scenarios", "dropped_scenarios"):
        if not isinstance(impact.get(field), list):
            errors.append(f"impact.{field} must be a list")
    if not isinstance(impact.get("acknowledged_empty"), bool):
        errors.append("impact.acknowledged_empty must be a boolean")

    candidates = impact.get("candidates")
    if isinstance(candidates, list):
        for idx, candidate in enumerate(candidates):
            if not isinstance(candidate, dict):
                errors.append(f"impact.candidates[{idx}] must be an object")
                continue
            for field in ("flow", "evidence"):
                if not isinstance(candidate.get(field), str) or not candidate[field].strip():
                    errors.append(f"impact.candidates[{idx}].{field} must be a non-empty string")
            if candidate.get("source") not in IMPACT_SOURCES:
                errors.append(
                    f"impact.candidates[{idx}].source must be sweep, declared, or both"
                )
            if not isinstance(candidate.get("existing_tests", []), list):
                errors.append(f"impact.candidates[{idx}].existing_tests must be a list")

    dropped = impact.get("dropped_scenarios")
    if isinstance(dropped, list):
        for idx, drop in enumerate(dropped):
            if not isinstance(drop, dict):
                errors.append(f"impact.dropped_scenarios[{idx}] must be an object")
                continue
            for field in ("name", "reason"):
                if not isinstance(drop.get(field), str) or not drop[field].strip():
                    errors.append(
                        f"impact.dropped_scenarios[{idx}].{field} must be a non-empty string"
                    )

    impact_resolved = (
        stage in IMPACT_RESOLVED_STAGES
        or resume_target in {"brainstorm", "design", "review", "automation", "automation-review", "finish", "done"}
    )
    if impact_resolved and impact_reason == "not-run":
        errors.append("impact.reason must record an outcome once the run moves past impact")

    conversion = _require_object(data.get("conversion"), "conversion", errors)
    conversion_status = conversion.get("status")
    if conversion_status not in CONVERSION_STATUSES:
        errors.append("conversion.status must be not-run, pending, or approved")
    converted = conversion.get("converted")
    if not isinstance(converted, list):
        errors.append("conversion.converted must be a list")
    else:
        if converted and conversion_status == "not-run":
            errors.append("conversion.status not-run cannot carry converted entries")
        for idx, entry in enumerate(converted):
            if not isinstance(entry, dict):
                errors.append(f"conversion.converted[{idx}] must be an object")
                continue
            manual_test = entry.get("manual_test")
            if not isinstance(manual_test, str) or not ISSUE_RE.match(manual_test):
                errors.append(
                    f"conversion.converted[{idx}].manual_test must be a Jira key like MOM-1234"
                )
            for field in ("scenarios", "deviations"):
                if not isinstance(entry.get(field), list):
                    errors.append(f"conversion.converted[{idx}].{field} must be a list")
            if entry.get("mode") not in CONVERSION_MODES:
                errors.append(f"conversion.converted[{idx}].mode must be link or overwrite")

    review = _require_object(data.get("review"), "review", errors)
    review_status = review.get("status")
    if review_status not in REVIEW_STATUSES:
        errors.append("review.status must be pending, passed, or changes-requested")
    review_required = (
        stage in REVIEW_REQUIRED_STAGES
        or resume_target in {"automation", "automation-review", "finish", "done"}
    )
    if review_required and review_status != "passed":
        errors.append("review.status must be passed before automation, finish, or done")
    if automation_status == "deferred" and review_status != "passed":
        errors.append("review.status must be passed before automation can be deferred")
    if review_status == "changes-requested" and resume_target not in {"design", "review"}:
        errors.append("review.status changes-requested must route back to design or review")
    for field in ("findings", "decisions"):
        if not isinstance(review.get(field), list):
            errors.append(f"review.{field} must be a list")

    if review_status == "passed" and isinstance(candidates, list):
        approved = impact.get("approved_scenarios")
        approved = approved if isinstance(approved, list) else []
        dropped_list = dropped if isinstance(dropped, list) else []
        if candidates and not approved and not dropped_list:
            errors.append(
                "impact.candidates must be covered by approved_scenarios or dropped_scenarios "
                "before review passes"
            )
        if not candidates and impact.get("ran") is True and not impact.get("acknowledged_empty"):
            errors.append(
                "impact.acknowledged_empty must be true when the sweep ran and found no candidates"
            )

    run_dir = path.resolve().parent
    workspace = _workspace_root(run_dir)
    artifacts = _require_object(data.get("artifacts"), "artifacts", errors)
    design_required = (
        stage in DESIGN_REQUIRED_STAGES
        or resume_target in {"review", "automation", "automation-review", "finish", "done"}
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

    related = coverage.get("related_issues")
    if not isinstance(related, list):
        errors.append("coverage.related_issues must be a list")
    else:
        for raw in related:
            if not isinstance(raw, str) or not ISSUE_RE.match(raw):
                errors.append(f"coverage.related_issues entry is not a Jira key: {raw!r}")

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
