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


def main() -> int:
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        test_clean_skill_has_no_errors(tmp)
        test_shared_file_linking_out_is_an_error(tmp)
        test_stage_linking_to_stage_is_an_error(tmp)
        test_links_inside_code_fences_are_ignored(tmp)
        test_stage_may_link_to_a_shared_leaf(tmp)
    print()
    if FAILURES:
        print(f"{len(FAILURES)} check(s) failed")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
