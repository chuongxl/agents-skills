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

## Artifact Path Guard (Run After Every Skill Call In This Stage)

`brainstorming` and `writing-plans` expose **no path parameter** — each hardcodes its output path
inside its own SKILL.md (`docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md` and
`docs/superpowers/plans/YYYY-MM-DD-<feature-name>.md`). Passing the pipeline path is an instruction
they may or may not follow, and every downstream stage keys off the pipeline path, so the
instruction alone is never enough.

After each of the two skill calls below, before doing anything else:

1. Check the pipeline path (`specs/<feature_folder>/spec.md` or `.../plan.md`). If the file is
   there, continue.
2. If it is not, look for the skill's default output — the newest matching file under
   `docs/superpowers/specs/` or `docs/superpowers/plans/` created during this run.
3. If found, move it to the pipeline path (`mkdir -p` the folder first) and log the relocation.
   Remove the now-empty default directory only if this run created it.
4. If neither path holds a file, the skill did not produce its artifact — re-run it once with the
   path stated more explicitly. Only a second failure is reportable.

This guard is deterministic and mandatory. Never assume the path instruction was honored, and never
carry a "the skill said it saved it" claim forward without checking the file.

## Step 1 — `brainstorming`

Pass into the skill:

- the compact Jira brief (or requirement text) from Stage 01
- open questions from Jira intake, as clarification seeds
- Project Context `summary` from Stage 01
- **the exact output path**: `specs/<feature_folder>/spec.md`
- an instruction **not to commit** the design document — the pipeline owns commits (Stage 04/05).
  If it commits anyway, log it and continue; never treat that as an error.

Interaction mode:

- **Default mode**: allow the skill's interactive Q&A and section-by-section approval. This *is*
  the clarification interview — do not additionally run a separate clarify step.
  **Fallback (default mode only)**: if `brainstorming` produced the design spec *without* running
  its interactive approval (no questions asked, or approval was skipped), the design spec has not
  been approved by a human. Do not proceed on the delegated gate alone — run the Interview Flow in
  [review-interview.md](review-interview.md) against the design spec once, then continue.
- **`--yolo` mode**: instruct the skill to auto-answer every clarifying question from the intake
  brief, choose the recommended option at each decision point, and skip all approval gates.
  State this explicitly in the skill input. The fallback above does not apply.

`brainstorming` carries a `<HARD-GATE>` blocking implementation until a human approves the design.
It is honored, not bypassed. In `--yolo`, `speckit-auto` is the approver: auto-approval **is** the
approval event, and the gate is satisfied once the design document is written and its self-review
is clean. State that in the skill input so it does not wait for a human message. Never end a
`--yolo` turn waiting on this gate.

Exit criteria: the design spec file exists at the exact path above (verified by the Artifact Path
Guard, not assumed) and its self-review found no placeholders or contradictions.

## Step 2 — `writing-plans`

Pass into the skill:

- the finalized design spec path from Step 1
- Project Context `summary`, `repo_map`, and any relevant cached guidelines from `loaded_guidelines`
- **the exact output path**: `specs/<feature_folder>/plan.md`
- an instruction to choose the execution style at Stage 03 (do not let it start implementing here)

Interaction mode: `writing-plans` ends with an "Execution Handoff" that asks the user to pick
between subagent-driven and inline execution, then invokes the chosen skill. Suppress that handoff
in **both** modes — Stage 03 owns the choice (see its Execution Style Selection) and must not be
entered from inside `writing-plans`. Treat the handoff text as data, not as a question to relay.

Exit criteria: the plan file exists at the exact path (verified by the Artifact Path Guard above,
not assumed), every task names its target workspace from `repo_map`, and the mandatory self-review
below has passed.

## Mandatory Self-Review Gate (checklist + analyze equivalent)

Before leaving Stage 02, verify explicitly and record the result:

1. **Spec coverage** — every requirement in the design spec maps to at least one plan task.
2. **Placeholder scan** — no `TODO`, `TBD`, `...`, or stub content in spec or plan.
3. **Consistency** — no conflicts, gaps, or ambiguities between the design spec and the plan
   (types, names, API contracts, file paths agree).
4. **Workspace assignment** — every task has a `workspace` from `repo_map`.

This check is read-only. If it flags anything, fix it at the source (re-run `brainstorming` for
spec issues, `writing-plans` for plan issues) and re-verify before Stage 03. Retry exhaustion
follows global rule 10a: the same check failing 3 consecutive times stops and reports.

Re-run this gate after **any** Stage 02 artifact regeneration, including one triggered from
Stage 03 or Stage 04. It fires no interview, so it never violates the Stage 03 no-stop rule.

## Payload Budget + Large Scope Partitioning

Payload budget: global rule 8 ([../shared/global-rules.md](../shared/global-rules.md)).

If the requirement is large or task volume is high, load
[../shared/partitioning.md](../shared/partitioning.md) and apply it: invoke `writing-plans` once per
package, merge the slices into the single plan file, then run the self-review gate once globally
after the merge (not per package).

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
  separate interview for it (see the Fallback in Step 1 for when it did not run). The plan's
  approval is the Stage 03 Entry Step confirmation below — do not run a separate post-`writing-plans`
  interview on top of it.
- **YOLO mode**: no interviews. Self-review the step output; if it fails, re-run the step
  (max 2 retries).

> ⚠️ These review behaviors apply **only to the steps in this file**. Stage 03 is a NO-STOP ZONE
> (global rule 11) — no interviews, no gates, in either mode.

## Restart Routing from Human Feedback (Default mode)

- Requirement intent change → re-run `brainstorming`
- Solution/architecture change → re-run `writing-plans` (plan structure section)
- Task/detail change → re-run `writing-plans` (task breakdown only)

## Stage 03 Entry Step (mandatory handoff)

Reaching the end of Stage 02 is **never** a stop condition on its own.

**Default mode** — one confirmation, and only this one. It **is** the plan's approval gate:
the routine post-`writing-plans` interview is folded into it, so never ask both back-to-back,
and never add a follow-up question after `Start implementation`.

1. Ask via the host's ask tool (`ask_user` on Copilot, `question` on OpenCode, `AskUser` on Claude
   Code): "Stage 02 complete (design spec + plan). Start implementation (Stage 03)?"
   Choices: `Start implementation`, `Request changes`.
2. `Start implementation` → discard Stage 02 files and `review-interview.md` from context and
   invoke [stage-03-implement-and-code-review-loop.md](stage-03-implement-and-code-review-loop.md)
   **immediately, in the same turn**. Do not summarize, do not ask anything else, do not wait for
   another user message.
3. `Request changes` → capture the feedback (including any forward constraints the user states
   here — this is where constraints are collected, not after approval), apply Restart Routing
   above, re-run the affected step and the Mandatory Self-Review Gate, then ask this question
   again.

**`--yolo` mode** — skip the confirmation entirely. Once the self-review gate passes, enter
Stage 03 immediately in the same turn.
