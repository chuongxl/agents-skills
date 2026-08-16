# Stage 02: Spec/Design Flow

Load this only while executing stages:
`speckit.specify -> speckit.clarify -> speckit.plan -> speckit.checklist -> speckit.tasks -> speckit.analyze`

Also load: [review-interview.md](review-interview.md) (default mode only; discard at Stage 03 entry).

## Stage Order (must not skip)

1. `speckit.specify`
2. `speckit.clarify`
3. `speckit.plan`
4. `speckit.checklist`
5. `speckit.tasks`
6. `speckit.analyze`

## Invocation Method (Critical)

Call stages directly via the resolved host channel (see
[../shared/host-adaptation.md](../shared/host-adaptation.md)):

- **GitHub Copilot / Claude Code** — repo slash commands (`/speckit.specify`, `/speckit.clarify`,
  `/speckit.plan`, `/speckit.checklist`, `/speckit.tasks`, `/speckit.analyze`) —
  `stage_invocation_mode` is `slash-agent`.
- **OpenCode** — the `skill` tool by each stage's resolved skill name (`speckit.specify`, …);
  OpenCode has no skill slash commands.

Never attempt `task` with a `speckit.*` agent_type on any host.

Never emit a capability disclaimer before attempting these — make the stage invocation now
(SKILL.md premise applies here too).

## Prompt Wiring Rules

Use the artifact digest (≤500 tokens, see [../shared/artifact-digest.md](../shared/artifact-digest.md))
as the prompt shortcut for every stage call below. The digest carries summary, ACs, architecture,
and task status. Only `speckit.clarify` and `speckit.analyze` need the full spec on disk; the
others work from the digest alone.

- `specify`: requirement text (or normalized Jira intake output) **+ Project Context `summary`**
- `clarify`: current `spec.md` (full read — needs detail for clarification)
- `plan`: artifact digest **+ Project Context `summary`, `repo_map`, and any relevant cached guidelines from `loaded_guidelines`**
- `checklist`: artifact digest — quality checklist against the summarized requirements
- `tasks`: artifact digest **+ `repo_map`** — every task must declare its target workspace
- `analyze`: `spec.md`, `plan.md`, `tasks.md` — full read-only consistency check; report conflicts/gaps/ambiguities

If `speckit.analyze` reports issues, fix at source (`specify/clarify/plan/checklist/tasks`) and rerun `speckit.analyze` before Stage 03.

## Payload Budget + Large Scope Partitioning

Payload budget: global rule 8 ([../shared/global-rules.md](../shared/global-rules.md)).

If requirements are large or task volume is high, load
[../shared/partitioning.md](../shared/partitioning.md) and apply it, with these stage bindings:

- `speckit.plan` → plan slices per package, merged into one `plan.md`.
- `speckit.checklist` → checklist slices merged into one requirement-quality checklist.
- `speckit.tasks` → tasks per package merged into one `tasks.md` with explicit ordering.
- `speckit.analyze` → run per package when large, then one final global read-only pass.

## Repository-Aware Task Assignment

When `speckit.tasks` runs, each task entry **must** include a `workspace` field derived from `repo_map`:

- Backend tasks (domain, application, infrastructure, API) → target the `backend` workspace
- Frontend tasks (UI components, pages, state) → target the `frontend` workspace
- BFF tasks (aggregation, gateway routes) → target the `bff` workspace
- Database tasks (migrations, schema) → target the `database` workspace
- Shared tasks (config, utilities, types) → target the `shared` workspace
- For single-repo projects (`layout = "single-repo"`), all tasks target `.`

Before naming any file, class, method, or API contract in `speckit.plan` or `speckit.tasks`,
check `linked_guidelines` from the Project Context and load the relevant cached guideline
(use the stem name to find a match). If it is already in `loaded_guidelines`, use the cached copy.

Never assign a task without consulting `repo_map` from the Project Context loaded in Stage 01.

## Review Behavior Per Stage

- **Default mode**: run post-stage interview (review-interview.md) and capture feedback/constraints.
- **Default mode / specify only**: if `speckit.specify` output is unclear, run the engineer clarification interview from `review-interview.md`, rerun `speckit.specify`, then continue.
- **Default mode / analyze only**: do **not** run a separate post-stage interview. Its approval is
  subsumed by the Stage 03 Entry Step confirmation below — never ask both back-to-back.
- **YOLO mode**: self-review stage output; if failed, rerun stage (max 2 retries).

> ⚠️ These review behaviors apply **only to the stages in this file**. Stage 03 is a NO-STOP ZONE (global rule 11) — no interviews, no gates, in either mode.

## Restart Routing from Human Feedback (Default mode)

- Requirement intent change -> restart from `speckit.specify`
- Solution/architecture change -> restart from `speckit.plan`
- Task/detail change -> restart from `speckit.tasks`

## Mandatory Self-Review Gate (both modes, before leaving Stage 02)

Runs in **default and `--yolo` mode**, after `speckit.analyze` and after any restart routing.
This is a read-only check on the produced artifacts — it is not an interview.

1. **Consistency** — assert the last `speckit.analyze` run reported no conflicts, gaps, or
   ambiguities. Do not re-derive that analysis here.
2. **Spec coverage** — every requirement in `spec.md` maps to at least one task in `tasks.md`
   (required by global rule 10a; `speckit.analyze` is a consistency check and does not
   guarantee this).
3. **Placeholder scan** — no `TODO`, `TBD`, `...`, or stub content in `spec.md`, `plan.md`,
   or `tasks.md`.
4. **Workspace assignment** — every task in `tasks.md` has a `workspace` from `repo_map`.

If any check fails, fix it at the source (`specify`/`clarify`/`plan`/`checklist`/`tasks`), re-run
`speckit.analyze`, and re-verify. Retry exhaustion follows global rule 10a: the same check failing
3 consecutive times stops and reports.

Re-run this gate after **any** Stage 02 artifact regeneration, including one triggered from
Stage 03 or Stage 04. It is read-only and fires no interview, so it never violates the Stage 03
no-stop rule.

Record the result. Do not enter Stage 03 with a failing check in either mode.

## Stage 03 Entry Step (mandatory handoff)

Reaching the end of Stage 02 is **never** a stop condition on its own.

**Default mode** — one confirmation, and only this one. Never add a follow-up question after
`Start implementation`:

1. Ask via the host's ask tool (`ask_user` on Copilot, `question` on OpenCode, `AskUser` on Claude
   Code): "Stage 02 complete (spec, plan, tasks, analyze). Start implementation
   (Stage 03)?" Choices: `Start implementation`, `Request changes`.
2. `Start implementation` → discard Stage 02 files and `review-interview.md` from context and
   invoke [stage-03-implement-and-code-review-loop.md](stage-03-implement-and-code-review-loop.md)
   **immediately, in the same turn**. Do not summarize, do not ask anything else, do not wait for
   another user message.
3. `Request changes` → capture the feedback (including any forward constraints the user states
   here — this is where constraints are collected, not after approval), apply Restart Routing
   above, re-run the affected stages through to `speckit.analyze` and the self-review gate, then
   ask this question again.

**`--yolo` mode** — skip the confirmation entirely. Once the self-review gate passes, enter
Stage 03 immediately in the same turn.

## Persist Run-State Before Stage Transition

After the self-review gate passes and before (or immediately after) the Stage 03 entry step,
save the run-state to `<worktree_path>/.speckit/run-state.json`:

- Set `current_stage: "stage-03"` (about to enter) and `stage_02_completed_at` to now.
- Update `spec_path`, `plan_path`, `tasks_path` if they changed during this stage.
- Format: see [../shared/run-state.md](../shared/run-state.md).
