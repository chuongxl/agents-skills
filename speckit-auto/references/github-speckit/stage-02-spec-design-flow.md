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

Call stages directly via repo-installed slash commands (`/speckit.specify`, `/speckit.clarify`,
`/speckit.plan`, `/speckit.checklist`, `/speckit.tasks`, `/speckit.analyze`) —
`stage_invocation_mode` is always `slash-agent`; never attempt `task` with a `speckit.*` agent_type.

Never emit a capability disclaimer before attempting these — call the slash command now (SKILL.md premise applies here too).

## Prompt Wiring Rules

- `specify`: requirement text (or normalized Jira intake output) **+ Project Context `summary`**
- `clarify`: current `spec.md`
- `plan`: finalized `spec.md` **+ Project Context `summary`, `repo_map`, and any relevant cached guidelines from `loaded_guidelines`**
- `checklist`: finalized `spec.md` — generate a quality checklist ("unit tests for your requirements") to confirm the spec is complete, clear, and consistent before task breakdown
- `tasks`: spec + plan context **+ `repo_map`** — every task must declare its target workspace
- `analyze`: `spec.md`, `plan.md`, `tasks.md` — read-only consistency check across artifacts; report conflicts/gaps/ambiguities

If `speckit.analyze` reports issues, fix at source (`specify/clarify/plan/checklist/tasks`) and rerun `speckit.analyze` before Stage 03.

## Payload Budget Rules (Stage 02)

For every Stage 02 invocation, keep payload compact:

- Include only the current stage input plus the minimal required context from previous artifacts.
- Prefer section excerpts over full-document dumps.
- Reuse cached Project Context from Stage 01; do not reload or restate unchanged guideline text.
- Never carry forward long review prose when a concise delta is enough.

## Large Scope Partitioning (Plan/Checklist/Tasks/Analyze)

If requirements are large or task volume is high, split the work into packages and process in batches.

### Package Strategy

1. Build `work_packages[]` by capability and `workspace` from `repo_map`.
2. For each package, include only:
   - package goal
   - relevant spec/plan sections
   - target workspace and constraints
3. Invoke the repo stage agent multiple times (one package per invocation) until all packages complete.

### Parallel vs Sequential

- **Parallel**: packages with no dependency links and no shared file ownership.
- **Sequential**: packages with dependency/order constraints (topological order).

### Stage-specific Application

- `speckit.plan`: create plan slices per package, then merge into one coherent `plan.md` with dependencies.
- `speckit.checklist`: generate checklist slices per package and merge into one requirement-quality checklist.
- `speckit.tasks`: generate tasks per package, then merge into one `tasks.md` with explicit ordering.
- `speckit.analyze`: run per package when large; then run one final global read-only consistency pass.

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

> ⚠️ These review behaviors apply **only to the stages in this file**. Stage 03 is a NO-STOP ZONE — no interviews, no gates in either mode.

## Restart Routing from Human Feedback (Default mode)

- Requirement intent change -> restart from `speckit.specify`
- Solution/architecture change -> restart from `speckit.plan`
- Task/detail change -> restart from `speckit.tasks`

## Mandatory Self-Review Gate (both modes, before leaving Stage 02)

Runs in **default and `--yolo` mode**, after `speckit.analyze` and after any restart routing.
This is a read-only check on the produced artifacts — it is not an interview.

1. **Spec coverage** — every requirement in `spec.md` maps to at least one task in `tasks.md`.
2. **Placeholder scan** — no `TODO`, `TBD`, `...`, or stub content in `spec.md`, `plan.md`,
   or `tasks.md`.
3. **Consistency** — no conflicts, gaps, or ambiguities between spec, plan, and tasks
   (types, names, API contracts, file paths agree). `speckit.analyze` output must be clean.
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

1. Ask via `ask_user`: "Stage 02 complete (spec, plan, tasks, analyze). Start implementation
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
