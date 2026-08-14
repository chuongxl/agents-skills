#!/usr/bin/env python3
"""Validate every skill in this repository against SKILL_SPEC.md.

Stdlib only — no third-party YAML dependency, so CI needs no install step.
Parses the frontmatter subset actually used by skills: scalars, quoted
scalars, block scalars (| and >), inline lists, block lists, and one level
of nested maps.

Usage:
    python3 tools/validate_skills.py
    python3 tools/validate_skills.py --skill speckit-auto
    python3 tools/validate_skills.py --json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
VERSION_RE = re.compile(r"^\d+\.\d+(\.\d+)?$")
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
README_VERSION_RE = re.compile(r"\bv(\d+\.\d+(?:\.\d+)?)\b")

TOP_LEVEL_KEYS = {
    "name",
    "description",
    "compatibility",
    "metadata",
    "license",
    "allowed-tools",
}
REQUIRED_KEYS = {"name", "description", "compatibility", "metadata"}

DESCRIPTION_MIN = 40
DESCRIPTION_MAX = 1024

NON_SKILL_DIRS = {"tools", "docs", "node_modules"}


# --------------------------------------------------------------------------
# Minimal YAML-subset parser
# --------------------------------------------------------------------------


class FrontmatterError(Exception):
    pass


def _strip_scalar(raw: str) -> str:
    raw = raw.strip()
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in "\"'":
        return raw[1:-1]
    return raw


def _parse_inline_list(raw: str) -> list[str]:
    inner = raw.strip()[1:-1].strip()
    if not inner:
        return []
    return [_strip_scalar(part) for part in inner.split(",")]


def _indent_of(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def parse_frontmatter(text: str) -> dict:
    """Parse the leading `---` delimited block into a nested dict."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise FrontmatterError("file does not start with a `---` frontmatter delimiter")

    try:
        end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    except StopIteration:
        raise FrontmatterError("frontmatter block is never closed with `---`") from None

    return _parse_block(lines[1:end], base_indent=0)


def _parse_block(lines: list[str], base_indent: int) -> dict:
    result: dict = {}
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip() or line.lstrip().startswith("#"):
            i += 1
            continue

        indent = _indent_of(line)
        if indent < base_indent:
            break

        if ":" not in line:
            raise FrontmatterError(f"unparseable frontmatter line: {line.strip()!r}")

        key, _, rest = line.strip().partition(":")
        key = key.strip()
        rest = rest.strip()
        i += 1

        # Block scalar: `key: |` or `key: >`
        if rest in ("|", ">", "|-", ">-", "|+", ">+"):
            body, i = _consume_indented(lines, i, indent)
            joined = (
                "\n".join(body)
                if rest.startswith("|")
                else " ".join(part.strip() for part in body if part.strip())
            )
            result[key] = joined.strip()
            continue

        # Inline list
        if rest.startswith("[") and rest.endswith("]"):
            result[key] = _parse_inline_list(rest)
            continue

        # Inline scalar
        if rest:
            result[key] = _strip_scalar(rest)
            continue

        # Nested block: map or list
        body, i = _consume_indented(lines, i, indent)
        if not body:
            result[key] = ""
        elif body[0].lstrip().startswith("- "):
            result[key] = [
                _strip_scalar(item.lstrip()[2:]) for item in body if item.strip()
            ]
        else:
            result[key] = _parse_block(body, base_indent=_indent_of(body[0]))

    return result


def _consume_indented(lines: list[str], start: int, parent_indent: int) -> tuple[list[str], int]:
    body: list[str] = []
    i = start
    while i < len(lines):
        line = lines[i]
        if line.strip() and _indent_of(line) <= parent_indent:
            break
        body.append(line)
        i += 1
    while body and not body[-1].strip():
        body.pop()
    if body:
        strip = min(_indent_of(line) for line in body if line.strip())
        body = [line[strip:] if line.strip() else "" for line in body]
    return body, i


# --------------------------------------------------------------------------
# Link extraction
# --------------------------------------------------------------------------


def strip_code(text: str) -> str:
    """Blank out fenced blocks and inline code so example links aren't checked."""
    text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    text = re.sub(r"~~~.*?~~~", "", text, flags=re.DOTALL)
    text = re.sub(r"`[^`\n]*`", "", text)
    return text


def relative_links(text: str) -> list[str]:
    links = []
    for match in LINK_RE.finditer(strip_code(text)):
        target = match.group(1).split("#")[0].strip()
        if not target or target.startswith(
            ("http://", "https://", "mailto:", "vscode:", "#", "<")
        ):
            continue
        links.append(target)
    return links


# --------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------


@dataclass
class Result:
    skill: str
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def discover_skills(root: Path) -> list[Path]:
    return sorted(
        path
        for path in root.iterdir()
        if path.is_dir()
        and not path.name.startswith(".")
        and path.name not in NON_SKILL_DIRS
        and (path / "SKILL.md").is_file()
    )


def readme_versions(root: Path) -> dict[str, str]:
    """Map skill name -> version declared in the root README skills table."""
    readme = root / "README.md"
    if not readme.is_file():
        return {}
    versions: dict[str, str] = {}
    for line in readme.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            continue
        match = re.search(r"\[([a-z0-9-]+)\]\(\./\1/README\.md\)", line)
        if not match:
            continue
        version = README_VERSION_RE.search(line)
        if version:
            versions[match.group(1)] = version.group(1)
    return versions


def validate_skill(skill_dir: Path, declared_versions: dict[str, str]) -> Result:
    name = skill_dir.name
    result = Result(skill=name)
    skill_md = skill_dir / "SKILL.md"

    if not NAME_RE.match(name):
        result.errors.append(f"folder name {name!r} is not lowercase kebab-case")

    try:
        meta = parse_frontmatter(skill_md.read_text(encoding="utf-8"))
    except FrontmatterError as exc:
        result.errors.append(f"SKILL.md: {exc}")
        return result

    for key in sorted(REQUIRED_KEYS - set(meta)):
        result.errors.append(f"SKILL.md: missing required frontmatter key {key!r}")

    for key in sorted(set(meta) - TOP_LEVEL_KEYS):
        result.errors.append(f"SKILL.md: unknown frontmatter key {key!r} (see SKILL_SPEC.md)")

    declared_name = meta.get("name")
    if declared_name and declared_name != name:
        result.errors.append(
            f"SKILL.md: name {declared_name!r} does not match folder name {name!r}"
        )

    description = meta.get("description")
    if isinstance(description, str):
        length = len(description.strip())
        if length < DESCRIPTION_MIN:
            result.errors.append(
                f"SKILL.md: description is {length} chars, minimum is {DESCRIPTION_MIN}"
            )
        elif length > DESCRIPTION_MAX:
            result.errors.append(
                f"SKILL.md: description is {length} chars, maximum is {DESCRIPTION_MAX}"
            )
    elif "description" in meta:
        result.errors.append("SKILL.md: description must be a string")

    compatibility = meta.get("compatibility")
    if compatibility is not None and not isinstance(compatibility, (str, dict)):
        result.errors.append("SKILL.md: compatibility must be a string or a map")

    metadata = meta.get("metadata")
    if metadata is None:
        pass  # already reported as missing
    elif not isinstance(metadata, dict):
        result.errors.append("SKILL.md: metadata must be a map")
    else:
        if not str(metadata.get("author", "")).strip():
            result.errors.append("SKILL.md: metadata.author is required and must be non-empty")
        version = str(metadata.get("version", "")).strip()
        if not version:
            result.errors.append("SKILL.md: metadata.version is required")
        elif not VERSION_RE.match(version):
            result.errors.append(
                f"SKILL.md: metadata.version {version!r} is not MAJOR.MINOR[.PATCH]"
            )
        elif name in declared_versions and declared_versions[name] != version:
            result.errors.append(
                f"root README declares v{declared_versions[name]} "
                f"but SKILL.md declares v{version}"
            )
        elif name not in declared_versions:
            result.warnings.append("skill is not listed in the root README skills table")

    if not (skill_dir / "README.md").is_file():
        result.errors.append("missing README.md")

    for doc in sorted(skill_dir.rglob("*.md")):
        rel = doc.relative_to(skill_dir)
        for link in relative_links(doc.read_text(encoding="utf-8")):
            target = (doc.parent / link).resolve()
            if not target.exists():
                result.errors.append(f"{rel}: broken link -> {link}")
            elif not target.is_relative_to(skill_dir.resolve()):
                result.errors.append(
                    f"{rel}: link escapes the skill folder -> {link} "
                    "(skills must be self-contained; see SKILL_SPEC.md)"
                )

    return result


def validate_repo_docs(root: Path) -> Result:
    result = Result(skill="<repo docs>")
    docs = list(root.glob("*.md")) + list((root / "docs").glob("*.md"))
    for doc in sorted(docs):
        for link in relative_links(doc.read_text(encoding="utf-8")):
            if not (doc.parent / link).resolve().exists():
                result.errors.append(
                    f"{doc.relative_to(root)}: broken link -> {link}"
                )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate skills against SKILL_SPEC.md")
    parser.add_argument("--skill", help="validate a single skill by folder name")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    parser.add_argument("--root", default=str(REPO_ROOT), help="repository root")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    skills = discover_skills(root)
    if args.skill:
        skills = [s for s in skills if s.name == args.skill]
        if not skills:
            print(f"error: no skill named {args.skill!r}", file=sys.stderr)
            return 1

    declared = readme_versions(root)
    results = [validate_skill(s, declared) for s in skills]
    if not args.skill:
        results.append(validate_repo_docs(root))

    if args.json:
        print(
            json.dumps(
                {
                    "ok": all(r.ok for r in results),
                    "results": [
                        {"skill": r.skill, "errors": r.errors, "warnings": r.warnings}
                        for r in results
                    ],
                },
                indent=2,
            )
        )
        return 0 if all(r.ok for r in results) else 1

    errors = warnings = 0
    for r in results:
        print(f"{'PASS' if r.ok else 'FAIL'}  {r.skill}")
        for message in r.errors:
            print(f"        error:   {message}")
            errors += 1
        for message in r.warnings:
            print(f"        warning: {message}")
            warnings += 1

    print(f"\n{len(results)} checked · {errors} error(s) · {warnings} warning(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
