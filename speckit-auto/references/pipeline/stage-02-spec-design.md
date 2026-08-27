# Stage 02: Spec / Design (Provider-Agnostic)

Already in context: `SKILL.md`, the run contract, the provider adapter, Stage 01 output. Load
nothing else unless a step says to.

Stage order and per-step identity come from the adapter's Stage Skill Map: github-speckit runs
`specify → clarify → plan → checklist → tasks → analyze` in fixed order; superpowers runs
`brainstorming` (= specify + clarify) then `writing-plans` (= plan + checklist + tasks + analyze).
Never skip, bypass, or reorder in either mode.

Invoke each step via the `skill` tool (run contract, Invocation Channel). After every call apply
the adapter's Step Completion Protocol — never proceed until the current step's artifact is
confirmed on disk. An unresolvable skill is a provider validation failure → adapter install
recovery, not a stop.

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

Applies after each `brainstorming` / `writing-plans` call — see the adapter's "Artifact Path
Guard". The instruction alone is never sufficient; always check the file.

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

**On `Request changes`:** capture the feedback verbatim, apply Restart Routing (see Review
Behavior → Default mode), re-run the affected steps through the Mandatory Self-Review Gate, then
present this gate again. Repeat until the user explicitly approves; never skip the gate on a
later pass.

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
`docs(<artifact_id>): add spec, plan, and tasks` — load
[../shared/commit.md](../shared/commit.md) now (first commit of the run). Already-clean tree →
skip per the conditional-commit rule (success path). A failed commit/push here is a stage failure
— stop with the exact error; never enter Stage 03 without this succeeding (or being a legitimate
no-op).

Then discard Stage 02 interview context, drop the loaded guideline files that Stage 03 will not
need, and load [stage-03-implement-review.md](stage-03-implement-review.md) **immediately, in the
same turn** — no summary, no other questions, no waiting for another user message.