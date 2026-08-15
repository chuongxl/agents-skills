# github-speckit: Provider-Specific Rules

Adds to [../shared/global-rules.md](../shared/global-rules.md). Never weakens it.

1. For `speckit.specify`, `speckit.clarify`, `speckit.plan`, `speckit.checklist`, `speckit.tasks`, `speckit.analyze`, `speckit.implement`, and `speckit.converge`, always use the **repository-installed** GitHub Speckit agents from this repo — never a global or external Speckit variant.
2. If the repository-installed Speckit is missing, Stage 01 runs install recovery: fetch the install guide, ask the user once (`Install GitHub Speckit` / `Stop`), and on `Install` perform the install, `specify init . --integration copilot`, run `/speckit.constitution`, re-check, then continue in the same turn. On `Stop`, halt and report that installation is required. Only a concrete install/init failure stops the run otherwise.
3. `stage_invocation_mode` is always `slash-agent`. Invoke stages as repo slash commands (`/speckit.specify`, …). Never attempt the `task` tool with a `speckit.*` agent_type — it always fails with `Unknown agent_type`.
4. Map user wording `speckit.implementation` to the repo agent `speckit.implement`.
5. Stage 03 order is fixed: run `speckit.implement → speckit.converge` repeatedly until converge reports no gaps, then run `speckit-code-review`; after that, loop `speckit.implement → speckit-code-review` until review status is `pass`.
6. Stage 02 order is fixed: `specify → clarify → plan → checklist → tasks → analyze`.
7. Artifacts use the Spec Kit layout `specs/<issue_id>-<short_title>/` (see Stage 01).

## Invocation

Invoke each stage as the repo-installed slash command (for example `/speckit.specify`), run as a
real command in the current turn.
