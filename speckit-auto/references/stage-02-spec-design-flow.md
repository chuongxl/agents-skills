# Stage 02: Spec/Design Flow

Load this only while executing stages:
`speckit.specify -> speckit.clarify -> speckit.plan -> speckit.tasks -> speckit.analyze -> speckit.converge`

Also load: [review-interview.md](review-interview.md) (default mode only; discard at Stage 03 entry).

## Stage Order (must not skip)

1. `speckit.specify`
2. `speckit.clarify`
3. `speckit.plan`
4. `speckit.tasks`
5. `speckit.analyze`
6. `speckit.converge`

## Prompt Wiring Rules

- `specify`: requirement text (or normalized Jira intake output) **+ Project Context `summary`**
- `clarify`: current `spec.md`
- `plan`: finalized `spec.md` **+ Project Context `summary`, `repo_map`, and any relevant cached guidelines from `loaded_guidelines`**
- `tasks`: spec + plan context **+ `repo_map`** — every task must declare its target workspace
- `analyze`: `spec.md`, `plan.md`, `tasks.md`
- `converge`: artifacts + current codebase, append remaining unbuilt work to `tasks.md`

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
- **YOLO mode**: self-review stage output; if failed, rerun stage (max 2 retries).

> ⚠️ These review behaviors apply **only to the stages in this file**. Stage 03 is a NO-STOP ZONE — no interviews, no gates in either mode.

## Restart Routing from Human Feedback (Default mode)

- Requirement intent change -> restart from `speckit.specify`
- Solution/architecture change -> restart from `speckit.plan`
- Task/detail change -> restart from `speckit.tasks`
