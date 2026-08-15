# Skill Specification

The contract every skill in this repository must satisfy. Enforced by
[`tools/validate_skills.py`](tools/validate_skills.py) and the
[validate-skills](.github/workflows/validate-skills.yml) CI workflow.

## Folder Layout

```
<skill-name>/
├── SKILL.md          # required — the skill definition, source of truth
├── README.md         # required — human documentation
├── references/       # optional — files loaded on demand by SKILL.md
├── assets/           # optional — templates, configs, static resources
└── scripts/          # optional — executable helpers
```

Rules:

- `<skill-name>` is lowercase kebab-case: `^[a-z0-9]+(-[a-z0-9]+)*$`.
- The folder name **must** equal the `name` field in `SKILL.md` frontmatter.
- A skill folder is any top-level directory containing a `SKILL.md`.
- Directories starting with `.` and the `tools/` and `docs/` directories are not skills.

## Frontmatter

`SKILL.md` must open with a YAML frontmatter block delimited by `---` on the
first line and a matching `---` terminator.

### Required keys

| Key | Type | Constraint |
|-----|------|-----------|
| `name` | string | kebab-case, equals the folder name |
| `description` | string | 40–1024 characters; states what the skill does **and** when to use it |
| `compatibility` | string \| map | free-form string, or a map of `<agent>: <string>` |
| `metadata` | map | must contain `author` and `version` |
| `metadata.author` | string | non-empty |
| `metadata.version` | string | semver-ish: `MAJOR.MINOR[.PATCH]` |

### Optional keys

| Key | Type | Notes |
|-----|------|-------|
| `license` | string | SPDX identifier, e.g. `MIT` |
| `allowed-tools` | string \| list | tools the skill is permitted to call |
| `metadata.*` | any | additional free-form metadata |

No key outside this table is permitted at the top level. This keeps the
frontmatter machine-readable across GitHub Copilot, Claude, and local agents.

### Example

```yaml
---
name: speckit-code-review
description: |
  Deep line-by-line code review against the feature spec at specs/<feature>/spec.md.
  Use when validating an implementation against its specification.
compatibility:
  github-copilot: "Auto-discovered from ~/.agents/skills/. Invoked via the skill tool."
license: MIT
allowed-tools: bash glob grep view create edit
metadata:
  author: Alex Nguyen
  version: "0.0.2"
---
```

## Description Guidance

The `description` is the only text an agent sees when deciding whether to load
the skill. It must answer two questions:

1. **What** does the skill do?
2. **When** should it be used? — include concrete trigger phrases.

Descriptions under 40 characters cannot carry both and are rejected.

## Links

Every relative Markdown link in `SKILL.md`, `README.md`, and `references/**.md`
must resolve to a file that exists. Links inside fenced code blocks and inline
backticks are ignored, since those are illustrative rather than navigational.

## Self-Containment

No link may resolve to a path **outside** its own skill folder. A skill is
installed by copying its folder, so a link to a sibling skill breaks the moment
the skill is installed on its own.

`../` is fine as long as it stays inside the skill — for example,
`references/shared/commit.md` linked from `references/github-speckit/stage-04.md`.
Refer to other skills by name in prose instead of linking to their files.

## Version Consistency

The root [`README.md`](README.md) skills table carries a `vX.Y.Z` badge per
skill. It must match `metadata.version` in that skill's `SKILL.md`.

## Running the Validator

```bash
python3 tools/validate_skills.py          # validate every skill
python3 tools/validate_skills.py --skill speckit-auto
python3 tools/validate_skills.py --json    # machine-readable output
```

Exit code `0` means every check passed; `1` means at least one error.
Warnings never fail the build.
