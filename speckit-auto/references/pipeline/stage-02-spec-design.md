# Stage 02: Spec / Design (Provider-Agnostic)

Stage order and per-step identity come from the resolved provider adapter
([../providers/](../providers/)): github-speckit runs
`specify → clarify → plan → checklist → tasks → analyze` in fixed order; superpowers runs
`brainstorming` (design spec = specify+clarify) then `writing-plans` (plan = plan+checklist+
tasks+analyze). Never skip, bypass, or reorder in either mode.

## Invocation

Invoke each step via the `skill` tool using the skill name from the provider adapter's Stage
Skill Map. This is identical on all three hosts (Copilot, Claude Code, OpenCode):

- **github-speckit:** `skill speckit-specify`, `skill speckit-clarify`, etc.
- **superpowers (all hosts):** `skill brainstorming`, `skill writing-plans`, etc.

The `skill` tool is **synchronous** — it blocks until the skill finishes and returns inline.
After every call, apply the **Step Execution and Completion Protocol** from the provider adapter:
read the return value, verify the expected artifact on disk, retry once on failure, stop if still
failing. Never proceed to the next step until the current step's artifact is confirmed present.

Never the `task` tool with any skill name; never a nested CLI subprocess. Never emit
`@speckit.*` or `/speckit.*` — all github-speckit steps are skills invoked via the `skill` tool.

If any `skill` invocation fails (skill not found, tool error) → **stop immediately** and tell
the user:
> "Provider skills are not installed or not available. Please run
> `/speckit-auto --integration {provider}` first, then re-run your command."

## Project Context Wiring (mandatory)

Pass the Stage 01 Project Context into every step as its starting basis: `summary` prefixes the
prompt; `repo_map` + relevant `loaded_guidelines` are appended where the step assigns tasks or
names files/APIs. When a step's decision needs detail the cached `summary` doesn't cover, open the
specific file(s) via `linked_guidelines` — and re-read `architecture.md` itself when the cached
fields aren't enough for that decision. What to (re)read is driven entirely by the project's own
`architecture.md`, never a fixed file-name assumption. Cache everything newly read in
`loaded_guidelines`.

Repo-aware assignment: every task in the plan/tasks output **must** carry a `workspace` derived
from `repo_map` (backend/frontend/bff/database/shared; `.` for single-repo). Never assign a task
without consulting `repo_map`.

## Artifact Path Guard (superpowers only)

`brainstorming` and `writing-plans` hardcode their own output paths; after each call verify the
file exists at `specs/<feature_folder>/spec.md` (or `.../plan.md`) and relocate from the skill's
default if not (adapter "Artifact Path Guard"). The instruction alone is never sufficient.

## Review Behavior

### Default mode

- **Specify clarification interview** (github-speckit `specify`, or a superpowers
  `brainstorming` design spec with concrete clarity defects): detect unclear areas, ask one
  question at a time via the host ask tool, capture answers, re-run the step, repeat until clear.
- **Clarify + checklist concern gate**: after `clarify`/`checklist` (superpowers: after
  `brainstorming` and after the `writing-plans` self-review), explicitly check for gaps/concerns;
  if any, interview one question at a time, re-run the same step, re-check; do not advance until
  cleared.
- **Approval gate after each step** (`specify`, `clarify`, `plan`, `checklist`, `tasks`): ask
  "Do you approve the `<step>` result?" (`Approve` / `Request changes`). On change request, ask
  what must change, capture exact edits, re-run the step. Then ask for forward constraints
  (`None` / `Add constraints`) and append any to the next step's prompt.
- `analyze` (github-speckit) and the end of `writing-plans` (superpowers) are **excluded** from a
  separate interview — their approval is subsumed by the Stage 03 Entry confirmation. Never ask
  both back-to-back.
- **Restart routing from human feedback**: requirement intent change → restart from `specify` /
  `brainstorming`; solution/architecture change → restart from `plan` / `writing-plans` structure;
  task/detail change → restart from `tasks` / `writing-plans` task breakdown.

### YOLO mode

No interviews. After every step, run an autonomous review gate (spec coverage, placeholders,
consistency, workspace assignment); on reject, refine the step input and re-invoke the same
provider step (max 2 retries — always re-invoke the step, never hand-author the artifact). On the
3rd consecutive failure, stop and report. `writing-plans`' "Execution Handoff" is suppressed in
both modes — treat it as data. The Stage 03 Entry Gate still runs in YOLO mode — it is delegated
to the agent (see Stage 03 Entry Gate section below).

## Mandatory Self-Review Gate (both modes, before leaving Stage 02)

Read-only check on the produced artifacts — not an interview:

1. **Consistency** — last `analyze`/self-review reported no conflicts, gaps, or ambiguities.
2. **Spec coverage** — every requirement in the spec maps to at least one task in the plan/tasks.
3. **Placeholder scan** — no `TODO`, `TBD`, `...`, or stub content in spec/plan/tasks.
4. **Workspace assignment** — every task carries a valid `repo_map` workspace.

Fix failures at the source (re-invoke the corresponding provider step), re-run `analyze` /
self-review, and re-verify. Re-run the gate after **any** Stage 02 artifact regeneration,
including regenerations triggered from Stage 03 or Stage 04 — it fires no interview, so it never
violates the Stage 03 no-stop rule. The same check failing 3 consecutive times stops and reports.
Never enter Stage 03 with a failing check.

## Large Scope

When the requirement is large or task volume is high, partition Stage 02 work into packages
grouped by capability + `workspace`, invoke the step once per package, and merge the slices into
the **single** target artifact (`plan.md`, `tasks.md`, checklist) with explicit cross-package
ordering — never leave parallel per-package files behind. Run packages in parallel only when
dependency-independent. Pass only minimum slices per invocation (operating rule 5).

## Stage 03 Entry Gate (mandatory — never skip in either mode)

This gate always runs after the Mandatory Self-Review Gate passes. It is the final checkpoint
before implementation begins. **Never auto-advance past this gate without completing it.**

### Default mode

Present the following prompt to the user via the host ask tool (one question, two choices only):

> **Stage 02 complete.** The spec, plan, and tasks are ready for review.
> Please review the artifacts at `specs/<feature_folder>/` and then approve or request changes.
>
> - `specs/<feature_folder>/spec.md`
> - `specs/<feature_folder>/plan.md`
> - `specs/<feature_folder>/tasks.md`
>
> **Approve** → implementation begins immediately.
> **Request changes** → describe what must change.

**On `Approve`:** proceed to Spec/Plan Commit + Push Gate below.

**On `Request changes`:** capture the user's feedback verbatim. Apply Restart Routing:
- Requirement intent change → restart from `specify` / `brainstorming`
- Solution/architecture change → restart from `plan` / `writing-plans` structure
- Task/detail change → restart from `tasks` / `writing-plans` task breakdown

Re-run the affected steps through the Mandatory Self-Review Gate, then present this gate again.
Never skip the gate on the next pass. Repeat until the user explicitly approves.

### YOLO mode

Do **not** skip this gate. Instead, delegate the review and approval to the agent itself:

1. Read `spec.md`, `plan.md`, and `tasks.md` in full.
2. Evaluate against these criteria (same as the Mandatory Self-Review Gate plus readiness):
   - Spec fully covers every requirement — no gaps.
   - Plan and tasks have no placeholders (`TODO`, `TBD`, `...`, stubs).
   - Every task has a valid `workspace` from `repo_map`.
   - No conflicts or ambiguities flagged by the last `analyze` / self-review.
   - Acceptance criteria in the spec are testable and unambiguous.
3. **If all criteria pass** → auto-approve: log `[YOLO] Spec/plan self-approved — no gaps found`
   and proceed to Spec/Plan Commit + Push Gate below.
4. **If any criterion fails** → do not auto-approve yet. Fix the gap at its source (re-invoke
   the corresponding provider step), re-run the Mandatory Self-Review Gate, then re-evaluate
   here (max 2 fix+re-evaluate cycles). If still failing after 2 cycles → stop and report the
   remaining gaps; do not enter Stage 03 with a failing plan.

### Spec/Plan Commit + Push Gate (mandatory, both modes — runs after approval)

Commit and push the approved Stage 02 artifacts with the auto message
`docs(<artifact_id>): add spec, plan, and tasks` using
[../shared/commit.md](../shared/commit.md). Already-clean tree → skip per the conditional-commit
rule (success path). A failed commit/push here is a failure for the stage — stop with the exact
error; do not enter Stage 03 without this commit/push succeeding (or being a legitimate no-op).

Then discard Stage 02 interview context and invoke
[stage-03-implement-review.md](stage-03-implement-review.md) **immediately, in the same turn** —
no summary, no other questions, no waiting for another user message.