# Provider Adapter: github-speckit (QA Edition)

Repository-installed GitHub Spec Kit skills adapted for `speckit-qa-auto`. Loaded when provider is `github-speckit`.

## Stage Skill Map

`speckit.*` steps are installed under `.github/skills/speckit-<command>/SKILL.md` and invoked via the `skill` tool.

| Pipeline step | Skill name | Output Artifact |
|---------------|------------|-----------------|
| Stage 02 Spec/Design | `speckit-specify` → `speckit-clarify` → `speckit-plan` | `specs/qa/<issue>/test-design.md`, `.feature` files |
| Stage 03 Automation | `speckit-implement` → `speckit-converge` | Derived automation test files |

All skills are executed synchronously via the `skill` tool.

## Verification & Recovery

- Validate that skills exist under `.github/skills/` on entry.
- If missing, run `specify init . --integration <host-key> --integration-options="--skills"`.
- If post-install validation fails, stop and direct user to restart host session.
