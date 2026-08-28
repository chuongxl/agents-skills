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
                "impact": {
                    "ran": True,
                    "reason": "ok",
                    "entities": [],
                    "declared": [],
                    "candidates": [],
                    "approved_scenarios": [],
                    "dropped_scenarios": [],
                    "acknowledged_empty": True,
                },
                "conversion": {"status": "not-run", "converted": []},
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
                "coverage": {"dedup": "ran", "xray": "available", "related_issues": []},
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
                "impact": {
                    "ran": True,
                    "reason": "ok",
                    "entities": [],
                    "declared": [],
                    "candidates": [],
                    "approved_scenarios": [],
                    "dropped_scenarios": [],
                    "acknowledged_empty": True,
                },
                "conversion": {"status": "not-run", "converted": []},
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
                "coverage": {"dedup": "not-run", "xray": "unavailable", "related_issues": []},
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
                "impact": {
                    "ran": True,
                    "reason": "ok",
                    "entities": [],
                    "declared": [],
                    "candidates": [],
                    "approved_scenarios": [],
                    "dropped_scenarios": [],
                    "acknowledged_empty": True,
                },
                "conversion": {"status": "not-run", "converted": []},
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
                "coverage": {"dedup": "ran", "xray": "available", "related_issues": []},
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
                "impact": {
                    "ran": True,
                    "reason": "ok",
                    "entities": [],
                    "declared": [],
                    "candidates": [],
                    "approved_scenarios": [],
                    "dropped_scenarios": [],
                    "acknowledged_empty": True,
                },
                "conversion": {"status": "not-run", "converted": []},
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
                "coverage": {"dedup": "not-run", "xray": "unavailable", "related_issues": []},
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
                "impact": {
                    "ran": True,
                    "reason": "ok",
                    "entities": [],
                    "declared": [],
                    "candidates": [],
                    "approved_scenarios": [],
                    "dropped_scenarios": [],
                    "acknowledged_empty": True,
                },
                "conversion": {"status": "not-run", "converted": []},
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
                "coverage": {"dedup": "ran", "xray": "available", "related_issues": []},
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
                "impact": {
                    "ran": True,
                    "reason": "ok",
                    "entities": [],
                    "declared": [],
                    "candidates": [],
                    "approved_scenarios": [],
                    "dropped_scenarios": [],
                    "acknowledged_empty": True,
                },
                "conversion": {"status": "not-run", "converted": []},
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
                "coverage": {"dedup": "not-run", "xray": "unavailable", "related_issues": []},
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
                "impact": {
                    "ran": True,
                    "reason": "ok",
                    "entities": [],
                    "declared": [],
                    "candidates": [],
                    "approved_scenarios": [],
                    "dropped_scenarios": [],
                    "acknowledged_empty": True,
                },
                "conversion": {"status": "not-run", "converted": []},
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
                "coverage": {"dedup": "ran", "xray": "available", "related_issues": []},
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
                "impact": {
                    "ran": True,
                    "reason": "ok",
                    "entities": [],
                    "declared": [],
                    "candidates": [],
                    "approved_scenarios": [],
                    "dropped_scenarios": [],
                    "acknowledged_empty": True,
                },
                "conversion": {"status": "not-run", "converted": []},
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
                "coverage": {"dedup": "not-run", "xray": "unavailable", "related_issues": []},
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


def test_impact_must_record_outcome(tmp: Path) -> None:
    print("impact-must-record-outcome")
    run_dir = tmp / "docs" / "qa" / "mom-1234"
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
                    "review": {"status": "not-run", "findings": []},
                },
                "impact": {
                    "ran": False,
                    "reason": "not-run",
                    "entities": [],
                    "declared": [],
                    "candidates": [],
                    "approved_scenarios": [],
                    "dropped_scenarios": [],
                    "acknowledged_empty": False,
                },
                "conversion": {"status": "not-run", "converted": []},
                "brainstorm": {
                    "status": "pending",
                    "approach": None,
                    "questions": [],
                    "confirmed_assumptions": [],
                    "rejected_approaches": [],
                },
                "review": {"status": "pending", "findings": [], "decisions": []},
                "artifacts": {"feature_files": [], "test_design": None},
                "coverage": {"dedup": "not-run", "xray": "unavailable", "related_issues": []},
            },
            indent=2,
        ),
    )
    result = run_script("validate-run-state.py", run_json)
    expect("impact still not-run past the gate exits nonzero", result.returncode == 1)
    expect("impact still not-run past the gate is explained", "impact.reason" in result.stderr)


def test_impact_candidates_must_be_satisfied(tmp: Path) -> None:
    print("impact-candidates-must-be-satisfied")
    run_dir = tmp / "docs" / "qa" / "mom-1234"
    write(
        run_dir / "invoice.feature",
        "Feature: Invoice\n\n  Scenario: show invoice\n    Given an invoice exists\n",
    )
    write(run_dir / "test-design.md", "# Test Design\n")
    run_json = write(
        run_dir / "run.json",
        json.dumps(
            {
                "issue": "MOM-1234",
                "stage": "review-passed",
                "resume_target": "finish",
                "automation": {
                    "status": "not-requested",
                    "requested": False,
                    "tool": None,
                    "skill": None,
                    "result": None,
                    "review": {"status": "not-run", "findings": []},
                },
                "impact": {
                    "ran": True,
                    "reason": "ok",
                    "entities": ["work_order_candidate"],
                    "declared": [],
                    "candidates": [
                        {
                            "flow": "RefreshWorkOrderCandidates",
                            "evidence": "src/work-order-candidate.graphql:123",
                            "writes": "work_order_candidate",
                            "existing_tests": [],
                            "source": "sweep",
                        }
                    ],
                    "approved_scenarios": [],
                    "dropped_scenarios": [],
                    "acknowledged_empty": False,
                },
                "conversion": {"status": "not-run", "converted": []},
                "brainstorm": {
                    "status": "approved",
                    "approach": "api-first",
                    "questions": [],
                    "confirmed_assumptions": [],
                    "rejected_approaches": [],
                },
                "review": {"status": "passed", "findings": [], "decisions": []},
                "artifacts": {
                    "feature_files": ["docs/qa/mom-1234/invoice.feature"],
                    "test_design": "docs/qa/mom-1234/test-design.md",
                },
                "coverage": {"dedup": "ran", "xray": "available", "related_issues": []},
            },
            indent=2,
        ),
    )
    result = run_script("validate-run-state.py", run_json)
    expect("undesigned impact candidate exits nonzero", result.returncode == 1)
    expect("undesigned impact candidate is explained", "impact.candidates" in result.stderr)


def test_related_issues_must_be_jira_keys(tmp: Path) -> None:
    print("related-issues-must-be-jira-keys")
    run_dir = tmp / "docs" / "qa" / "mom-1234"
    run_json = write(
        run_dir / "run.json",
        json.dumps(
            {
                "issue": "MOM-1234",
                "stage": "discovered",
                "resume_target": "impact",
                "automation": {
                    "status": "not-requested",
                    "requested": False,
                    "tool": None,
                    "skill": None,
                    "result": None,
                    "review": {"status": "not-run", "findings": []},
                },
                "impact": {
                    "ran": False,
                    "reason": "not-run",
                    "entities": [],
                    "declared": [],
                    "candidates": [],
                    "approved_scenarios": [],
                    "dropped_scenarios": [],
                    "acknowledged_empty": False,
                },
                "conversion": {"status": "not-run", "converted": []},
                "brainstorm": {
                    "status": "pending",
                    "approach": None,
                    "questions": [],
                    "confirmed_assumptions": [],
                    "rejected_approaches": [],
                },
                "review": {"status": "pending", "findings": [], "decisions": []},
                "artifacts": {"feature_files": [], "test_design": None},
                "coverage": {
                    "dedup": "not-run",
                    "xray": "unavailable",
                    "related_issues": ["mom-1100"],
                },
            },
            indent=2,
        ),
    )
    result = run_script("validate-run-state.py", run_json)
    expect("malformed related key exits nonzero", result.returncode == 1)
    expect("malformed related key is explained", "coverage.related_issues" in result.stderr)


def _deferred_run(review_status: str, automation: dict) -> dict:
    return {
        "issue": "MOM-1234",
        "stage": "finished",
        "resume_target": "done",
        "automation": automation,
        "impact": {
            "ran": True,
            "reason": "ok",
            "entities": [],
            "declared": [],
            "candidates": [],
            "approved_scenarios": [],
            "dropped_scenarios": [],
            "acknowledged_empty": True,
        },
        "conversion": {"status": "not-run", "converted": []},
        "brainstorm": {
            "status": "approved",
            "approach": "api-first",
            "questions": [],
            "confirmed_assumptions": [],
            "rejected_approaches": [],
        },
        "review": {"status": review_status, "findings": [], "decisions": []},
        "artifacts": {
            "feature_files": ["docs/qa/mom-1234/invoice.feature"],
            "test_design": "docs/qa/mom-1234/test-design.md",
        },
        "coverage": {"dedup": "ran", "xray": "available", "related_issues": []},
    }


def _deferred_automation(**overrides: object) -> dict:
    automation = {
        "status": "deferred",
        "requested": True,
        "deferred": {
            "reason": "implementation not merged yet",
            "resume_when": "MOM-1234 code is on the target branch",
        },
        "tool": None,
        "skill": None,
        "result": None,
        "review": {"status": "not-run", "findings": []},
    }
    automation.update(overrides)
    return automation


def _write_deferred(tmp: Path, data: dict) -> Path:
    run_dir = tmp / "docs" / "qa" / "mom-1234"
    write(
        run_dir / "invoice.feature",
        "Feature: Invoice\n\n  Scenario: show invoice\n    Given an invoice exists\n",
    )
    write(run_dir / "test-design.md", "# Test Design\n")
    return write(run_dir / "run.json", json.dumps(data, indent=2))


def test_deferred_automation_is_valid(tmp: Path) -> None:
    print("deferred-automation-is-valid")
    run_json = _write_deferred(tmp, _deferred_run("passed", _deferred_automation()))
    result = run_script("validate-run-state.py", run_json)
    expect("deferred automation exits 0", result.returncode == 0)
    expect("deferred automation reports ok", '"ok": true' in result.stdout)


def test_deferred_requires_passed_review(tmp: Path) -> None:
    print("deferred-requires-passed-review")
    data = _deferred_run("pending", _deferred_automation())
    data["stage"] = "reviewing"
    data["resume_target"] = "review"
    run_json = _write_deferred(tmp, data)
    result = run_script("validate-run-state.py", run_json)
    expect("deferring before review exits nonzero", result.returncode == 1)
    expect(
        "deferring before review is explained",
        "before automation can be deferred" in result.stderr,
    )


def test_deferred_requires_reason_and_resume_when(tmp: Path) -> None:
    print("deferred-requires-reason-and-resume-when")
    automation = _deferred_automation(deferred={"reason": "", "resume_when": "   "})
    run_json = _write_deferred(tmp, _deferred_run("passed", automation))
    result = run_script("validate-run-state.py", run_json)
    expect("empty deferral record exits nonzero", result.returncode == 1)
    expect("deferral reason is explained", "automation.deferred.reason" in result.stderr)
    expect("deferral resume_when is explained", "automation.deferred.resume_when" in result.stderr)


def test_deferred_block_needs_deferred_status(tmp: Path) -> None:
    print("deferred-block-needs-deferred-status")
    automation = _deferred_automation(status="not-run")
    run_json = _write_deferred(tmp, _deferred_run("passed", automation))
    result = run_script("validate-run-state.py", run_json)
    expect("stale deferral block exits nonzero", result.returncode == 1)
    expect(
        "stale deferral block is explained",
        "only valid when automation.status is deferred" in result.stderr,
    )


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
        test_impact_must_record_outcome(tmp / "impact-outcome")
        test_impact_candidates_must_be_satisfied(tmp / "impact-satisfied")
        test_related_issues_must_be_jira_keys(tmp / "related-keys")
        test_deferred_automation_is_valid(tmp / "deferred-valid")
        test_deferred_requires_passed_review(tmp / "deferred-review")
        test_deferred_requires_reason_and_resume_when(tmp / "deferred-record")
        test_deferred_block_needs_deferred_status(tmp / "deferred-stale")
        test_dedup_gherkin(tmp / "gherkin")
    print()
    if FAILURES:
        print(f"{len(FAILURES)} check(s) failed")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
