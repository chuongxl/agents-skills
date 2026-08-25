#!/usr/bin/env python3
"""Self-test for tools/validate_coupling.py.

Builds throwaway skill folders in a temp directory and asserts the checker
reports exactly the expected errors. Stdlib only; run with:

    python3 tools/test_validate_coupling.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from validate_coupling import check_skill  # noqa: E402

FAILURES: list[str] = []


def expect(label: str, condition: bool) -> None:
    if condition:
        print(f"ok   - {label}")
    else:
        print(f"FAIL - {label}")
        FAILURES.append(label)


def build(root: Path, files: dict[str, str]) -> Path:
    skill = root / "sample-skill"
    for rel, body in files.items():
        path = skill / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
    return skill


def test_clean_skill_has_no_errors(tmp: Path) -> None:
    skill = build(tmp / "clean", {
        "SKILL.md": "Router. See [stage 1](references/pipeline/stage-01.md).\n",
        "references/pipeline/stage-01.md": "Load [run state](../shared/run-state.md).\n",
        "references/shared/run-state.md": "The data contract. Links to nothing.\n",
    })
    expect("clean skill reports no errors", check_skill(skill) == [])


def test_shared_file_linking_out_is_an_error(tmp: Path) -> None:
    skill = build(tmp / "shared-links", {
        "SKILL.md": "Router.\n",
        "references/shared/run-state.md": "See [commit](commit.md).\n",
        "references/shared/commit.md": "Leaf.\n",
    })
    errors = check_skill(skill)
    expect("shared leaf linking to a sibling is one error", len(errors) == 1)
    expect("error names the offending file",
           "references/shared/run-state.md" in errors[0])


def test_stage_linking_to_stage_is_an_error(tmp: Path) -> None:
    skill = build(tmp / "stage-links", {
        "SKILL.md": "Router.\n",
        "references/pipeline/stage-01.md": "Then [stage 2](stage-02.md).\n",
        "references/pipeline/stage-02.md": "Leaf.\n",
    })
    errors = check_skill(skill)
    expect("stage linking to another stage is one error", len(errors) == 1)
    expect("error names both stage files",
           "stage-01.md" in errors[0] and "stage-02.md" in errors[0])


def test_links_inside_code_fences_are_ignored(tmp: Path) -> None:
    skill = build(tmp / "fenced", {
        "SKILL.md": "Router.\n",
        "references/shared/run-state.md": "```\n[commit](commit.md)\n```\n",
        "references/shared/commit.md": "Leaf.\n",
    })
    expect("a link inside a code fence is illustrative, not navigational",
           check_skill(skill) == [])


def test_stage_may_link_to_a_shared_leaf(tmp: Path) -> None:
    skill = build(tmp / "two-hop", {
        "SKILL.md": "Router.\n",
        "references/pipeline/stage-01.md": "Load [run state](../shared/run-state.md).\n",
        "references/shared/run-state.md": "Leaf.\n",
    })
    expect("a stage may load a shared leaf", check_skill(skill) == [])


def test_undeclared_backtick_citation_is_an_error(tmp: Path) -> None:
    skill = build(tmp / "cited", {
        "SKILL.md": "Router.\n",
        "references/pipeline/stage-01.md":
            "Loads: [run state](../shared/run-state.md).\n\n"
            "Commit per `commit.md`.\n",
        "references/shared/run-state.md": "Leaf.\n",
        "references/shared/commit.md": "Leaf.\n",
    })
    errors = check_skill(skill)
    expect("citing an undeclared leaf in backticks is one error", len(errors) == 1)
    expect("error names the leaf and the Loads line",
           errors and "commit.md" in errors[0] and "Loads:" in errors[0])


def test_declared_backtick_citation_is_accepted(tmp: Path) -> None:
    skill = build(tmp / "cited-ok", {
        "SKILL.md": "Router.\n",
        "references/pipeline/stage-01.md":
            "Loads: [run state](../shared/run-state.md),\n"
            "[commit](../shared/commit.md).\n\n"
            "Commit per `commit.md`.\n",
        "references/shared/run-state.md": "Leaf.\n",
        "references/shared/commit.md": "Leaf.\n",
    })
    expect("citing a leaf declared on a wrapped Loads: line is fine",
           check_skill(skill) == [])


def test_artifact_and_stage_filenames_are_not_citations(tmp: Path) -> None:
    skill = build(tmp / "artifacts", {
        "SKILL.md": "Router.\n",
        "references/pipeline/stage-01.md":
            "Loads: [run state](../shared/run-state.md).\n\n"
            "Write `ticket.md` and `execution-report.md`, then enter `stage-02.md`.\n",
        "references/pipeline/stage-02.md": "Leaf.\n",
        "references/shared/run-state.md": "Leaf.\n",
    })
    expect("artifact filenames and successor stage names are not leaf citations",
           check_skill(skill) == [])


def test_shared_leaf_citing_a_sibling_is_not_a_c3_error(tmp: Path) -> None:
    skill = build(tmp / "shared-cite", {
        "SKILL.md": "Router.\n",
        "references/shared/discovery.md": "See `impact-analysis.md` for the fourth sweep.\n",
        "references/shared/impact-analysis.md": "Leaf.\n",
    })
    expect("a leaf citing a sibling by name is how leaves refer to each other",
           check_skill(skill) == [])


def test_modular_layout_is_accepted(tmp: Path) -> None:
    skill = build(tmp / "modular-clean", {
        "SKILL.md":
            "Read [protocol](references/protocol.md), [resume](references/resume.md), "
            "and [adapter](adapters/playwright-bdd.md).\n",
        "references/protocol.md": "Artifact contract.\n",
        "references/resume.md": "Resume first.\n",
        "adapters/playwright-bdd.md": "Adapter contract.\n",
    })
    expect("modular references and adapters are accepted", check_skill(skill) == [])


def test_modular_reference_linking_to_adapter_is_an_error(tmp: Path) -> None:
    skill = build(tmp / "modular-ref-link", {
        "SKILL.md":
            "Read [protocol](references/protocol.md) and "
            "[adapter](adapters/playwright-bdd.md).\n",
        "references/protocol.md": "See [Playwright](../adapters/playwright-bdd.md).\n",
        "adapters/playwright-bdd.md": "Adapter contract.\n",
    })
    errors = check_skill(skill)
    expect("core references may not route to adapters", len(errors) == 1)
    expect("error names the reference and adapter",
           bool(errors)
           and "references/protocol.md" in errors[0]
           and "adapters/playwright-bdd.md" in errors[0])


def test_modular_unrouted_adapter_is_an_error(tmp: Path) -> None:
    skill = build(tmp / "modular-missing-route", {
        "SKILL.md": "Read [protocol](references/protocol.md).\n",
        "references/protocol.md": "Artifact contract.\n",
        "adapters/playwright-bdd.md": "Adapter contract.\n",
    })
    errors = check_skill(skill)
    expect("adapter files must be routed from SKILL.md", len(errors) == 1)
    expect("error names the unrouted adapter",
           bool(errors) and "adapters/playwright-bdd.md" in errors[0])


def main() -> int:
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        test_clean_skill_has_no_errors(tmp)
        test_shared_file_linking_out_is_an_error(tmp)
        test_stage_linking_to_stage_is_an_error(tmp)
        test_links_inside_code_fences_are_ignored(tmp)
        test_stage_may_link_to_a_shared_leaf(tmp)
        test_undeclared_backtick_citation_is_an_error(tmp)
        test_declared_backtick_citation_is_accepted(tmp)
        test_artifact_and_stage_filenames_are_not_citations(tmp)
        test_shared_leaf_citing_a_sibling_is_not_a_c3_error(tmp)
        test_modular_layout_is_accepted(tmp)
        test_modular_reference_linking_to_adapter_is_an_error(tmp)
        test_modular_unrouted_adapter_is_an_error(tmp)
    print()
    if FAILURES:
        print(f"{len(FAILURES)} check(s) failed")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
