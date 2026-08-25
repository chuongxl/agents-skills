#!/usr/bin/env python3
"""Enforce the reference-file coupling rules from the speckit-qa-auto design.

Legacy pipeline rules, from the original stage design:

  C1  A file under references/shared/ links to no other file in the skill.
      Shared files are leaves: they may be loaded, they load nothing.
  C2  A file under references/pipeline/ does not link to another file under
      references/pipeline/. Ordering belongs to the router, not to the stages.

  C3  A file under references/pipeline/ declares, on its `Loads:` line, every
      shared leaf it cites in backticks. The Loads line is the disclosure that
      lets a reader know the cost before paying it; a leaf cited but never
      declared is one read from memory instead of from the file, and a field
      name read from memory drifts.

      C3 reads citations, not links, because every link in a stage file already
      sits on that file's own Loads: line — a link-based check would be
      tautologically satisfied while real violations stood.

Modular protocol rules, from the thin-orchestrator redesign:

  C4  A direct file under references/ links to no other reference or adapter.
      Core references are independent protocol pages; they are loaded by the
      orchestrator, not by each other.
  C5  A file under adapters/ does not link to another adapter. Adapter choice is
      owned by the router.
  C6  Every direct references/*.md and adapters/*.md file is linked from
      SKILL.md. Progressive disclosure only works if entry routing is visible.

Opt-in per skill by explicit argument, so skills that were never designed
against these rules are left alone. Stdlib only; run with:

    python3 tools/validate_coupling.py speckit-qa-auto
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from validate_skills import relative_links  # noqa: E402

SHARED = "references/shared"
PIPELINE = "references/pipeline"
REFERENCES = "references"
ADAPTERS = "adapters"

LOADS_RE = re.compile(r"^Loads:(.*?)(?:\n\n|\Z)", re.S | re.M)
CITATION_RE = re.compile(r"`([a-z0-9][a-z0-9-]*\.md)`")


def _declared_loads(path: Path, text: str) -> set[str]:
    """Basenames named on the file's `Loads:` line, which may wrap."""
    match = LOADS_RE.search(text)
    if not match:
        return set()
    return {
        link.split("#", 1)[0].strip().rsplit("/", 1)[-1]
        for link in relative_links(match.group(0))
    }


def _markdown_files(skill_dir: Path) -> list[Path]:
    return sorted(p for p in skill_dir.rglob("*.md") if p.is_file())


def _is_direct_child(rel: str, parent: str) -> bool:
    prefix = parent + "/"
    return rel.startswith(prefix) and rel[len(prefix):].count("/") == 0


def _skill_routes(skill_dir: Path) -> set[str]:
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        return set()
    routes: set[str] = set()
    for link in relative_links(skill_md.read_text(encoding="utf-8")):
        target = link.split("#", 1)[0].strip()
        if not target or not target.endswith(".md"):
            continue
        resolved = (skill_md.parent / target).resolve()
        try:
            routes.add(resolved.relative_to(skill_dir.resolve()).as_posix())
        except ValueError:
            continue
    return routes


def check_skill(skill_dir: Path) -> list[str]:
    """Return a list of coupling errors; empty means the skill is clean."""
    errors: list[str] = []
    routes = _skill_routes(skill_dir)
    for path in _markdown_files(skill_dir):
        rel = path.relative_to(skill_dir).as_posix()
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            errors.append(f"{rel}: unreadable ({exc})")
            continue

        for link in relative_links(text):
            target = link.split("#", 1)[0].strip()
            if not target or not target.endswith(".md"):
                continue
            resolved = (path.parent / target).resolve()
            try:
                target_rel = resolved.relative_to(skill_dir.resolve()).as_posix()
            except ValueError:
                continue  # outside the skill: validate_skills.py owns that error

            if rel.startswith(SHARED + "/"):
                errors.append(
                    f"{rel}: shared files are leaves and must link to nothing "
                    f"inside the skill, but links to {target_rel}"
                )
            elif rel.startswith(PIPELINE + "/") and target_rel.startswith(PIPELINE + "/"):
                errors.append(
                    f"{rel}: stage files must not reference each other, "
                    f"but links to {target_rel}"
                )
            elif _is_direct_child(rel, REFERENCES) and (
                target_rel.startswith(REFERENCES + "/")
                or target_rel.startswith(ADAPTERS + "/")
            ):
                errors.append(
                    f"{rel}: core references are leaves and must be routed by "
                    f"SKILL.md, but links to {target_rel}"
                )
            elif rel.startswith(ADAPTERS + "/") and target_rel.startswith(ADAPTERS + "/"):
                errors.append(
                    f"{rel}: adapter files must not route to other adapters, "
                    f"but links to {target_rel}"
                )

        if not rel.startswith(PIPELINE + "/"):
            continue
        declared = _declared_loads(path, text)
        shared_dir = skill_dir / SHARED
        for name in sorted(set(CITATION_RE.findall(text))):
            # Membership in references/shared/ is what separates a leaf citation
            # from an artifact filename; no allow-list to keep in sync.
            if not (shared_dir / name).is_file():
                continue
            if name not in declared:
                errors.append(
                    f"{rel}: cites {SHARED}/{name} but does not name it on its "
                    f"`Loads:` line — a cited leaf that goes undeclared is read "
                    f"from memory instead of from the file"
                )

    for path in _markdown_files(skill_dir):
        rel = path.relative_to(skill_dir).as_posix()
        if (
            _is_direct_child(rel, REFERENCES)
            or rel.startswith(ADAPTERS + "/") and rel.endswith(".md")
        ) and rel not in routes:
            errors.append(f"{rel}: not routed from SKILL.md")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check reference-file coupling rules for the named skills"
    )
    parser.add_argument("skills", nargs="+", help="skill folder paths or names")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    report: dict[str, list[str]] = {}
    for name in args.skills:
        skill_dir = Path(name)
        if not skill_dir.is_dir():
            skill_dir = repo_root / name
        if not skill_dir.is_dir():
            report[name] = [f"no such skill folder: {name}"]
            continue
        report[skill_dir.name] = check_skill(skill_dir)

    failed = any(errors for errors in report.values())
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        for skill, errors in report.items():
            if errors:
                print(f"{skill}: {len(errors)} coupling error(s)")
                for err in errors:
                    print(f"  - {err}")
            else:
                print(f"{skill}: ok")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
