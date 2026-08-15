#!/usr/bin/env python3
"""Self-test for tools/validate_skills.py.

Builds throwaway skill folders in a temp directory and asserts the validator
reports exactly the expected errors. Stdlib only; run with:

    python3 tools/test_validate_skills.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from validate_skills import (  # noqa: E402
    FrontmatterError,
    parse_frontmatter,
    readme_versions,
    relative_links,
    validate_skill,
)

GOOD_FRONTMATTER = """---
name: {name}
description: |
  A well formed sample skill used only by the validator self-test suite.
  Use when exercising the validator against a known-good skill definition.
compatibility:
  github-copilot: "Auto-discovered from ~/.agents/skills/."
license: MIT
allowed-tools: [bash, view]
metadata:
  author: Test Author
  version: "1.2.3"
---

# Sample
"""

failures: list[str] = []


def check(condition: bool, label: str) -> None:
    if condition:
        print(f"  ok   {label}")
    else:
        print(f"  FAIL {label}")
        failures.append(label)


def make_skill(root: Path, name: str, frontmatter: str, readme: bool = True) -> Path:
    skill = root / name
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(frontmatter, encoding="utf-8")
    if readme:
        (skill / "README.md").write_text("# doc\n", encoding="utf-8")
    return skill


def test_parser() -> None:
    print("parse_frontmatter")
    meta = parse_frontmatter(GOOD_FRONTMATTER.format(name="sample-skill"))
    check(meta["name"] == "sample-skill", "reads a scalar")
    check(meta["description"].startswith("A well formed"), "reads a block scalar")
    check(isinstance(meta["compatibility"], dict), "reads a nested map")
    check(meta["allowed-tools"] == ["bash", "view"], "reads an inline list")
    check(meta["metadata"]["version"] == "1.2.3", "strips quotes in nested map")

    for bad, label in [
        ("no frontmatter here\n", "rejects a missing delimiter"),
        ("---\nname: x\n", "rejects an unclosed block"),
    ]:
        try:
            parse_frontmatter(bad)
            check(False, label)
        except FrontmatterError:
            check(True, label)


def test_links() -> None:
    print("relative_links")
    text = (
        "[a](./real.md) [b](https://x.dev) [c](#anchor)\n"
        "`[d](inline-code.md)`\n"
        "```\n[e](fenced.md)\n```\n"
    )
    check(relative_links(text) == ["./real.md"], "ignores urls, anchors, and code")


def test_validation() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        print("validate_skill")

        good = make_skill(root, "good-skill", GOOD_FRONTMATTER.format(name="good-skill"))
        result = validate_skill(good, {"good-skill": "1.2.3"})
        check(result.ok, "accepts a valid skill")

        result = validate_skill(good, {"good-skill": "9.9.9"})
        check(
            any("root README declares" in e for e in result.errors),
            "detects README/SKILL version drift",
        )

        result = validate_skill(good, {})
        check(
            any("not listed in the root README" in w for w in result.warnings),
            "warns when unlisted in README, without failing",
        )
        check(result.ok, "an unlisted skill is a warning, not an error")

        mismatch = make_skill(
            root, "mismatch-skill", GOOD_FRONTMATTER.format(name="other-name")
        )
        result = validate_skill(mismatch, {})
        check(
            any("does not match folder name" in e for e in result.errors),
            "detects a name/folder mismatch",
        )

        short = make_skill(
            root,
            "short-skill",
            "---\nname: short-skill\ndescription: too short\n"
            'compatibility: any\nmetadata:\n  author: A\n  version: "1.0"\n---\n',
        )
        result = validate_skill(short, {})
        check(
            any("minimum is" in e for e in result.errors),
            "rejects a too-short description",
        )

        noreadme = make_skill(
            root, "noreadme-skill", GOOD_FRONTMATTER.format(name="noreadme-skill"),
            readme=False,
        )
        result = validate_skill(noreadme, {})
        check(any("missing README.md" in e for e in result.errors), "requires a README")

        broken = make_skill(root, "broken-skill", GOOD_FRONTMATTER.format(name="broken-skill"))
        (broken / "README.md").write_text("[gone](./nowhere.md)\n", encoding="utf-8")
        result = validate_skill(broken, {})
        check(any("broken link" in e for e in result.errors), "detects a broken link")

        escaper = make_skill(root, "escaper-skill", GOOD_FRONTMATTER.format(name="escaper-skill"))
        (escaper / "README.md").write_text(
            "[outside](../good-skill/README.md)\n", encoding="utf-8"
        )
        result = validate_skill(escaper, {})
        check(
            any("escapes the skill folder" in e for e in result.errors),
            "detects a link escaping the skill folder",
        )

        internal = make_skill(
            root, "internal-skill", GOOD_FRONTMATTER.format(name="internal-skill")
        )
        (internal / "references").mkdir()
        (internal / "references" / "a.md").write_text("[up](../README.md)\n", encoding="utf-8")
        result = validate_skill(internal, {})
        check(result.ok, "allows ../ links that stay inside the skill folder")

        unknown = make_skill(
            root,
            "unknown-skill",
            GOOD_FRONTMATTER.format(name="unknown-skill").replace(
                "license: MIT", "license: MIT\nbogus: value"
            ),
        )
        result = validate_skill(unknown, {})
        check(
            any("unknown frontmatter key" in e for e in result.errors),
            "rejects an unknown frontmatter key",
        )

        badver = make_skill(
            root,
            "badver-skill",
            GOOD_FRONTMATTER.format(name="badver-skill").replace('"1.2.3"', '"v1"'),
        )
        result = validate_skill(badver, {})
        check(
            any("is not MAJOR.MINOR" in e for e in result.errors),
            "rejects a malformed version",
        )

        print("readme_versions")
        (root / "README.md").write_text(
            "| [good-skill](./good-skill/README.md) | desc | path | compat | trig | v1.2.3 / A |\n",
            encoding="utf-8",
        )
        check(
            readme_versions(root) == {"good-skill": "1.2.3"},
            "parses versions from the README table",
        )


def main() -> int:
    test_parser()
    test_links()
    test_validation()
    if failures:
        print(f"\n{len(failures)} self-test failure(s)")
        return 1
    print("\nall self-tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
