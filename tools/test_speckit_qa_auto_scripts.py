#!/usr/bin/env python3
"""Self-test for speckit-qa-auto helper scripts.

Builds throwaway QA artifact folders and tiny repository fixtures. Stdlib only;
run with:

    python3 tools/test_speckit_qa_auto_scripts.py
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL = REPO_ROOT / "speckit-qa-auto"

FAILURES: list[str] = []


def expect(label: str, condition: bool) -> None:
    if condition:
        print(f"ok   - {label}")
    else:
        print(f"FAIL - {label}")
        FAILURES.append(label)


def run_script(name: str, *args: str | Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SKILL / "scripts" / name), *(str(arg) for arg in args)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_validate_run_state(tmp: Path) -> None:
    print("validate-run-state")
    run_dir = tmp / "docs" / "qa" / "mom-1234"
    feature = write(
        run_dir / "invoice.feature",
        "Feature: Invoice\n\n  Scenario: show invoice\n    Given an invoice exists\n",
    )
    design = write(run_dir / "test-design.md", "# Test Design\n")
    run_json = write(
        run_dir / "run.json",
        json.dumps(
            {
                "issue": "MOM-1234",
                "stage": "review-passed",
                "resume_target": "automation",
                "automation": {
                    "status": "pending",
                    "requested": True,
                    "tool": None,
                    "skill": None,
                    "result": None,
                    "review": {
                        "status": "pending",
                        "findings": [],
                    },
                },
                "brainstorm": {
                    "status": "approved",
                    "approach": "api-first-plus-ui-smoke",
                    "questions": [],
                    "confirmed_assumptions": [],
                    "rejected_approaches": ["ui-heavy"],
                },
                "review": {
                    "status": "passed",
                    "findings": [],
                    "decisions": [],
                },
                "artifacts": {
                    "feature_files": [str(feature.relative_to(tmp))],
                    "test_design": str(design.relative_to(tmp)),
                },
                "coverage": {"dedup": "ran", "xray": "available"},
            },
            indent=2,
        ),
    )
    result = run_script("validate-run-state.py", run_json)
    expect("valid run.json exits 0", result.returncode == 0)
    expect("valid run.json reports ok", '"ok": true' in result.stdout)

    broken = json.loads(run_json.read_text(encoding="utf-8"))
    broken["stage"] = "stage-02"
    run_json.write_text(json.dumps(broken), encoding="utf-8")
    result = run_script("validate-run-state.py", run_json)
    expect("invalid stage exits nonzero", result.returncode == 1)
    expect("invalid stage is explained", "stage" in result.stderr)


def test_validate_pre_design_state(tmp: Path) -> None:
    print("validate-pre-design-state")
    run_dir = tmp / "docs" / "qa" / "mom-1234"
    write(run_dir / "ticket.md", "# MOM-1234\n")
    run_json = write(
        run_dir / "run.json",
        json.dumps(
            {
                "issue": "MOM-1234",
                "stage": "discovered",
                "resume_target": "brainstorm",
                "automation": {
                    "status": "not-requested",
                    "requested": False,
                    "tool": None,
                    "skill": None,
                    "result": None,
                    "review": {
                        "status": "not-run",
                        "findings": [],
                    },
                },
                "brainstorm": {
                    "status": "pending",
                    "approach": None,
                    "questions": [],
                    "confirmed_assumptions": [],
                    "rejected_approaches": [],
                },
                "review": {
                    "status": "pending",
                    "findings": [],
                    "decisions": [],
                },
                "artifacts": {"feature_files": [], "test_design": None},
                "coverage": {"dedup": "not-run", "xray": "unavailable"},
            },
            indent=2,
        ),
    )

    result = run_script("validate-run-state.py", run_json)
    expect("pre-design state exits 0", result.returncode == 0)
    expect("pre-design state reports ok", '"ok": true' in result.stdout)


def test_design_requires_brainstorm(tmp: Path) -> None:
    print("design-requires-brainstorm")
    run_dir = tmp / "docs" / "qa" / "mom-1234"
    feature = write(
        run_dir / "invoice.feature",
        "Feature: Invoice\n\n  Scenario: show invoice\n    Given an invoice exists\n",
    )
    design = write(run_dir / "test-design.md", "# Test Design\n")
    run_json = write(
        run_dir / "run.json",
        json.dumps(
            {
                "issue": "MOM-1234",
                "stage": "design-approved",
                "resume_target": "automation",
                "automation": {
                    "status": "pending",
                    "requested": True,
                    "tool": None,
                    "skill": None,
                    "result": None,
                    "review": {
                        "status": "pending",
                        "findings": [],
                    },
                },
                "brainstorm": {
                    "status": "pending",
                    "approach": None,
                    "questions": [],
                    "confirmed_assumptions": [],
                    "rejected_approaches": [],
                },
                "review": {
                    "status": "passed",
                    "findings": [],
                    "decisions": [],
                },
                "artifacts": {
                    "feature_files": [str(feature.relative_to(tmp))],
                    "test_design": str(design.relative_to(tmp)),
                },
                "coverage": {"dedup": "ran", "xray": "available"},
            },
            indent=2,
        ),
    )

    result = run_script("validate-run-state.py", run_json)
    expect("design without approved brainstorm exits nonzero", result.returncode == 1)
    expect("design without approved brainstorm is explained", "brainstorm.status" in result.stderr)


def test_brainstorm_approved_stage_requires_approved_status(tmp: Path) -> None:
    print("brainstorm-approved-stage-requires-approved-status")
    run_dir = tmp / "docs" / "qa" / "mom-1234"
    run_json = write(
        run_dir / "run.json",
        json.dumps(
            {
                "issue": "MOM-1234",
                "stage": "brainstorm-approved",
                "resume_target": "design",
                "automation": {
                    "status": "not-requested",
                    "requested": False,
                    "tool": None,
                    "skill": None,
                    "result": None,
                    "review": {
                        "status": "not-run",
                        "findings": [],
                    },
                },
                "brainstorm": {
                    "status": "pending",
                    "approach": None,
                    "questions": [],
                    "confirmed_assumptions": [],
                    "rejected_approaches": [],
                },
                "review": {
                    "status": "pending",
                    "findings": [],
                    "decisions": [],
                },
                "artifacts": {"feature_files": [], "test_design": None},
                "coverage": {"dedup": "not-run", "xray": "unavailable"},
            },
            indent=2,
        ),
    )

    result = run_script("validate-run-state.py", run_json)
    expect("brainstorm-approved with pending status exits nonzero", result.returncode == 1)
    expect("brainstorm-approved with pending status is explained", "brainstorm.status" in result.stderr)


def test_automation_requires_review_passed(tmp: Path) -> None:
    print("automation-requires-review-passed")
    run_dir = tmp / "docs" / "qa" / "mom-1234"
    feature = write(
        run_dir / "invoice.feature",
        "Feature: Invoice\n\n  Scenario: show invoice\n    Given an invoice exists\n",
    )
    design = write(run_dir / "test-design.md", "# Test Design\n")
    run_json = write(
        run_dir / "run.json",
        json.dumps(
            {
                "issue": "MOM-1234",
                "stage": "design-approved",
                "resume_target": "automation",
                "automation": {
                    "status": "pending",
                    "requested": True,
                    "tool": None,
                    "skill": None,
                    "result": None,
                    "review": {
                        "status": "pending",
                        "findings": [],
                    },
                },
                "brainstorm": {
                    "status": "approved",
                    "approach": "api-first-plus-ui-smoke",
                    "questions": [],
                    "confirmed_assumptions": [],
                    "rejected_approaches": [],
                },
                "review": {
                    "status": "pending",
                    "findings": [],
                    "decisions": [],
                },
                "artifacts": {
                    "feature_files": [str(feature.relative_to(tmp))],
                    "test_design": str(design.relative_to(tmp)),
                },
                "coverage": {"dedup": "ran", "xray": "available"},
            },
            indent=2,
        ),
    )

    result = run_script("validate-run-state.py", run_json)
    expect("automation without passed review exits nonzero", result.returncode == 1)
    expect("automation without passed review is explained", "review.status" in result.stderr)


def test_review_route_requires_design_artifacts(tmp: Path) -> None:
    print("review-route-requires-design-artifacts")
    run_dir = tmp / "docs" / "qa" / "mom-1234"
    run_json = write(
        run_dir / "run.json",
        json.dumps(
            {
                "issue": "MOM-1234",
                "stage": "brainstorm-approved",
                "resume_target": "review",
                "automation": {
                    "status": "not-requested",
                    "requested": False,
                    "tool": None,
                    "skill": None,
                    "result": None,
                    "review": {
                        "status": "not-run",
                        "findings": [],
                    },
                },
                "brainstorm": {
                    "status": "approved",
                    "approach": "api-first-plus-ui-smoke",
                    "questions": [],
                    "confirmed_assumptions": [],
                    "rejected_approaches": [],
                },
                "review": {
                    "status": "pending",
                    "findings": [],
                    "decisions": [],
                },
                "artifacts": {"feature_files": [], "test_design": None},
                "coverage": {"dedup": "not-run", "xray": "unavailable"},
            },
            indent=2,
        ),
    )

    result = run_script("validate-run-state.py", run_json)
    expect("review route without design artifacts exits nonzero", result.returncode == 1)
    expect("review route without design artifacts is explained", "artifacts" in result.stderr)


def test_implemented_automation_can_resume_to_review(tmp: Path) -> None:
    print("implemented-automation-can-resume-to-review")
    run_dir = tmp / "docs" / "qa" / "mom-1234"
    feature = write(
        run_dir / "invoice.feature",
        "Feature: Invoice\n\n  Scenario: show invoice\n    Given an invoice exists\n",
    )
    design = write(run_dir / "test-design.md", "# Test Design\n")
    run_json = write(
        run_dir / "run.json",
        json.dumps(
            {
                "issue": "MOM-1234",
                "stage": "automation-reviewing",
                "resume_target": "automation-review",
                "automation": {
                    "status": "implemented",
                    "requested": True,
                    "tool": "repo-test-runner",
                    "skill": None,
                    "result": "docs/qa/MOM-1234/automation-result.json",
                    "review": {
                        "status": "pending",
                        "findings": [],
                    },
                },
                "brainstorm": {
                    "status": "approved",
                    "approach": "api-first-plus-ui-smoke",
                    "questions": [],
                    "confirmed_assumptions": [],
                    "rejected_approaches": [],
                },
                "review": {
                    "status": "passed",
                    "findings": [],
                    "decisions": [],
                },
                "artifacts": {
                    "feature_files": [str(feature.relative_to(tmp))],
                    "test_design": str(design.relative_to(tmp)),
                },
                "coverage": {"dedup": "ran", "xray": "available"},
            },
            indent=2,
        ),
    )

    result = run_script("validate-run-state.py", run_json)
    expect("implemented automation can route to review", result.returncode == 0)


def test_adapter_field_is_rejected(tmp: Path) -> None:
    print("adapter-field-is-rejected")
    run_dir = tmp / "docs" / "qa" / "mom-1234"
    run_json = write(
        run_dir / "run.json",
        json.dumps(
            {
                "issue": "MOM-1234",
                "stage": "discovered",
                "resume_target": "brainstorm",
                "adapter": "playwright-bdd",
                "automation": {
                    "status": "not-requested",
                    "requested": False,
                    "tool": None,
                    "skill": None,
                    "result": None,
                    "review": {
                        "status": "not-run",
                        "findings": [],
                    },
                },
                "brainstorm": {
                    "status": "pending",
                    "approach": None,
                    "questions": [],
                    "confirmed_assumptions": [],
                    "rejected_approaches": [],
                },
                "review": {
                    "status": "pending",
                    "findings": [],
                    "decisions": [],
                },
                "artifacts": {"feature_files": [], "test_design": None},
                "coverage": {"dedup": "not-run", "xray": "unavailable"},
            },
            indent=2,
        ),
    )

    result = run_script("validate-run-state.py", run_json)
    expect("adapter field exits nonzero", result.returncode == 1)
    expect("adapter field is explained", "adapter" in result.stderr)


def test_dedup_gherkin(tmp: Path) -> None:
    print("dedup-gherkin")
    existing = write(
        tmp / "existing.feature",
        """
Feature: Candidate invoice

  @REQ_MOM-1200
  Scenario: attach invoice to candidate
    Given a candidate exists
    When I attach an invoice
    Then the invoice appears on the candidate
""".strip(),
    )
    candidate = write(
        tmp / "candidate.feature",
        """
Feature: Candidate invoice

  @REQ_MOM-1234
  Scenario: Attach invoice to candidate
    Given a candidate exists
    When I attach an invoice
    Then the invoice appears on the candidate

  Scenario: reject unsupported invoice type
    Given a candidate exists
    When I attach an unsupported invoice
    Then the attachment is rejected
""".strip(),
    )
    result = run_script("dedup-gherkin.py", "--existing", existing, "--candidate", candidate)
    expect("dedup exits 0", result.returncode == 0)
    if result.returncode != 0:
        return
    payload = json.loads(result.stdout)
    labels = {item["scenario"]: item["label"] for item in payload["scenarios"]}
    expect("exact normalized scenario is skipped", labels["Attach invoice to candidate"] == "SKIP")
    expect("new scenario is new", labels["reject unsupported invoice type"] == "NEW")


def main() -> int:
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        test_validate_run_state(tmp / "state")
        test_validate_pre_design_state(tmp / "pre-design")
        test_design_requires_brainstorm(tmp / "brainstorm-required")
        test_brainstorm_approved_stage_requires_approved_status(tmp / "brainstorm-approved-stage")
        test_automation_requires_review_passed(tmp / "review-required")
        test_review_route_requires_design_artifacts(tmp / "review-artifacts-required")
        test_implemented_automation_can_resume_to_review(tmp / "automation-review")
        test_adapter_field_is_rejected(tmp / "adapter-field")
        test_dedup_gherkin(tmp / "gherkin")
    print()
    if FAILURES:
        print(f"{len(FAILURES)} check(s) failed")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
