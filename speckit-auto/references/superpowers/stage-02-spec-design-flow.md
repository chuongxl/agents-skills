# Stage 02 (superpowers): Spec/Design Flow

Load this only while running `brainstorming` and `writing-plans`.
Also load: [review-interview.md](review-interview.md) (default mode only; discard at Stage 03 entry).

## Stage Order (must not skip)

1. `brainstorming` → design spec document
2. `writing-plans` → implementation plan

These two map onto the Spec Kit flow as follows:

| Spec Kit stage | superpowers coverage |
|----------------|----------------------|
| `specify` | `brainstorming` — design exploration + spec document |
| `clarify` | `brainstorming` — one-question-at-a-time clarification |
| `plan` | `writing-plans` — file structure + approach |
| `checklist` | `writing-plans` self-review — spec coverage + placeholder scan |
| `tasks` | `writing-plans` — bite-sized tasks with exact paths, code, verify steps |
| `analyze` | `writing-plans` self-review — consistency across spec/plan/tasks |

The `checklist` and `analyze` equivalents are **not optional**: they are enforced as the explicit
self-review gate below.

## Invocation Method (Critical)

Invoke `brainstorming` and `writing-plans` via the `skill` tool. Superpowers ships no slash commands
and no agents, and the `task` tool must never be used with a `superpowers:*` agent_type. Resolve
each skill name using the precedence in [provider-rules.md](provider-rules.md).

Never emit a capability disclaimer before attempting these — make the `skill` call now (the
SKILL.md Absolute Operating Premise applies here too).

## Step 1 — `brainstorming`

Pass into the skill:

- the compact Jira brief (or requirement text) from Stage 01
- open questions from Jira intake, as clarification seeds
- Project Context `summary` from Stage 01
- **the exact output path**: `specs/<feature_folder>/spec.md`

Interaction mode:

- **Default mode**: allow the skill's interactive Q&A and section-by-section approval. This *is*
  the clarification interview — do not additionally run a separate clarify step.
- **`--yolo` mode**: instruct the skill to auto-answer every clarifying question from the intake
  brief, choose the recommended option at each decision point, and skip all approval gates.
  State this explicitly in the skill input.

Exit criteria: the design spec file exists at the exact path above and its self-review found no
placeholders or contradictions.

## Step 2 — `writing-plans`

Pass into the skill:

- the finalized design spec path from Step 1
- Project Context `summary`, `repo_map`, and any relevant cached guidelines from `loaded_guidelines`
- **the exact output path**: `specs/<feature_folder>/plan.md`
- an instruction to choose the execution style at Stage 03 (do not let it start implementing here)

Interaction mode: in `--yolo`, skip its "subagent-driven vs inline" user choice — Stage 03 decides.

Exit criteria: the plan file exists at the exact path, every task names its target workspace from
`repo_map`, and the mandatory self-review below has passed.

## Mandatory Self-Review Gate (checklist + analyze equivalent)

Before leaving Stage 02, verify explicitly and record the result:

1. **Spec coverage** — every requirement in the design spec maps to at least one plan task.
2. **Placeholder scan** — no `TODO`, `TBD`, `...`, or stub content in spec or plan.
3. **Consistency** — no conflicts, gaps, or ambiguities between the design spec and the plan
   (types, names, API contracts, file paths agree).
4. **Workspace assignment** — every task has a `workspace` from `repo_map`.

This check is read-only. If it flags anything, fix it at the source (re-run `brainstorming` for
spec issues, `writing-plans` for plan issues) and re-verify before Stage 03.

## Prompt / Payload Budget Rules (Stage 02)

- Include only the current step's input plus minimal context from prior artifacts.
- Prefer section excerpts over full-document dumps.
- Reuse cached Project Context from Stage 01; never reload or restate unchanged guideline text.
- Never carry forward long review prose when a concise delta is enough.

## Large Scope Partitioning

If the requirement is large or task volume is high, split into packages.

1. Build `work_packages[]` by capability and `workspace` from `repo_map`.
2. For each package include only: package goal, relevant spec sections, target workspace, constraints.
3. Invoke `writing-plans` once per package, then merge the slices into one coherent
   plan file at the single target path, with explicit cross-package ordering and dependencies.
4. Parallel only for packages with no dependency links and no shared file ownership; otherwise
   sequential in topological order.
5. Run the self-review gate once globally after the merge, not only per package.

## Repository-Aware Task Assignment

Every plan task **must** carry a `workspace` derived from `repo_map`:

- Backend (domain, application, infrastructure, API) → `backend`
- Frontend (UI components, pages, state) → `frontend`
- BFF (aggregation, gateway routes) → `bff`
- Database (migrations, schema) → `database`
- Shared (config, utilities, types) → `shared`
- Single-repo projects (`layout = "single-repo"`) → `.`

Before naming any file, class, method, or API contract, check `linked_guidelines` from the Project
Context and load the relevant cached guideline (match by stem name). Reuse `loaded_guidelines` if
already cached. Never assign a task without consulting `repo_map`.

## Review Behavior Per Step

- **Default mode**: `brainstorming`'s own interactive approval is the design-spec review gate — no
  separate interview for it. After `writing-plans`, run the post-step interview
  (review-interview.md) and capture feedback.
- **YOLO mode**: no interviews. Self-review the step output; if it fails, re-run the step
  (max 2 retries).

> ⚠️ These review behaviors apply **only to the steps in this file**. Stage 03 is a NO-STOP ZONE —
> no interviews, no gates, in either mode.

## Restart Routing from Human Feedback (Default mode)

- Requirement intent change → re-run `brainstorming`
- Solution/architecture change → re-run `writing-plans` (plan structure section)
- Task/detail change → re-run `writing-plans` (task breakdown only)
