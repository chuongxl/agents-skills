# github-speckit: Provider-Specific Rules

Adds to [../shared/global-rules.md](../shared/global-rules.md). Never weakens it.
Also loads [../shared/host-adaptation.md](../shared/host-adaptation.md) for the per-host layout.

1. For `speckit.constitution`, `speckit.specify`, `speckit.clarify`, `speckit.plan`,
   `speckit.checklist`, `speckit.tasks`, `speckit.analyze`, `speckit.implement`, and
   `speckit.converge`, always use the **repository-installed** GitHub Speckit agents from this repo
   — never a global or external Speckit variant.
2. The install key and repo layout are host-dependent (see host-adaptation.md): Copilot → `copilot`
   (skills or commands mode), Claude Code → `claude` (skills in `.claude/skills/`), OpenCode →
   `opencode`. The `<host-key>` is resolved from host detection and is never user-provided.
   If the repository-installed Speckit is missing, Stage 01 runs install recovery: fetch the install
   guide, ask the user once (`Install GitHub Speckit` / `Stop`), and on `Install` perform the
   install, run `specify init . --integration <host-key>` as a mandatory success gate, run
   `speckit.constitution` through the host channel (Copilot: repo slash-agent, not `skill` tool),
   require `speckit.constitution` success, re-check, then continue in the same turn. All of this
   runs inside the Stage 01 linked worktree branch. On `Stop`, halt and report that installation is
   required. Only a concrete install/init/constitution failure stops the run otherwise.
2a. Even when install recovery is not needed, Stage 01 must still run `speckit.constitution` once
    through the github-speckit channel and require success before entering Stage 02. Never skip.
3. `stage_invocation_mode` is host-dependent:
   - **GitHub Copilot** — `slash-agent`: invoke repo slash commands (`/speckit.specify`, …). For
     `speckit.constitution` after install, use the repo slash-agent channel (not `skill` tool).
   - **Claude Code** — `slash-agent`: invoke repo slash commands (`/speckit.specify`, …), or via
     the `Skill` tool by resolved skill name.
   - **OpenCode** — `skill` tool only: invoke each stage by its resolved skill name. OpenCode has no skill slash commands.
   Never attempt the `task` tool with a `speckit.*` agent_type on any host — it always fails with `Unknown agent_type`.
4. Map user wording `speckit.implementation` to the repo agent `speckit.implement`.
5. Stage 03 order is fixed: run `speckit.implement → speckit.converge` repeatedly until converge reports no gaps, then run `speckit-code-review`; after that, loop `speckit.implement → speckit-code-review` until review status is `pass`.
6. Stage 02 order is fixed: `specify → clarify → plan → checklist → tasks → analyze`.
7. Artifacts use the Spec Kit layout `specs/<issue_id>-<short_title>/` (see Stage 01).
8. For github-speckit provider, Stage 02 and Stage 03 artifacts must be produced by github-speckit
   stage agents (`speckit.specify`, `speckit.clarify`, `speckit.plan`, `speckit.checklist`,
   `speckit.tasks`, `speckit.analyze`, `speckit.implement`, `speckit.converge`). `speckit-auto`
   must never synthesize spec/plan/tasks content itself.
9. If a required github-speckit stage cannot be invoked via the resolved host channel (slash-agent
   on Copilot/Claude, `skill` on OpenCode), stop and report the concrete invocation error. Do not
   continue with a manual fallback.

## Invocation

Invoke each stage via the resolved host channel — the repo slash command on Copilot and Claude Code
(for example `/speckit.specify`), or the `skill` tool by the stage's resolved skill name on OpenCode —
run as a real call in the current turn.
