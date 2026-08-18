# Stage 02: Spec / Design (Provider-Agnostic)

Stage order and per-step identity come from the resolved provider adapter
([../providers/](../providers/)): github-speckit runs
`specify → clarify → plan → checklist → tasks → analyze` in fixed order; superpowers runs
`brainstorming` (design spec = specify+clarify) then `writing-plans` (plan = plan+checklist+
tasks+analyze). Never skip, bypass, or reorder in either mode.

## Invocation

Invoke each step via the provider's resolved channel
(see [../shared/host-adaptation.md](../shared/host-adaptation.md) and the adapter):

- **GitHub Copilot:** emit `@speckit.<command> [args]` (agent call). Slash commands are **not
  visible** on Copilot — never use `/speckit.<command>` here.
- **Claude Code:** emit `/speckit.<command> [args]` (slash command, visible and callable). For
  skills-mode layout, the `Skill` tool is also valid.
- **OpenCode:** use the `skill` tool by the resolved on-disk skill name.
- **superpowers (all hosts):** use the `skill` tool for every superpowers skill.

On Copilot and Claude Code, each `@speckit.<command>` / `/speckit.<command>` call is a **turn
boundary** — the agent takes over the current turn; resume in the next turn, read the output, and
validate before invoking the next step. Never the `task` tool with a `speckit.*` agent_type;
never a nested CLI subprocess.

Before each provider step invocation in this stage, run provider availability validation. If
validation fails, trigger install recovery immediately for the resolved provider. If post-install
validation still fails, stop and ask the user to manually install/fix the provider or restart
Copilot / Claude Code / OpenCode, then re-run `speckit-auto`.

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
3rd consecutive failure, stop and report. `brainstorming`'s `<HARD-GATE>` is satisfied by this
self-approval in `--yolo` (auto-approval IS the approval event — never wait for a human message).
`writing-plans`' "Execution Handoff" is suppressed in both modes — treat it as data.

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

## Stage 03 Entry Step (mandatory handoff) + Spec/Plan Commit Gate

Reaching the end of Stage 02 is **never** a stop condition.

- **Default mode**: ask the ONE confirmation via the host ask tool: "Stage 02 complete (spec,
  plan, tasks). Start implementation (Stage 03)?" (`Start implementation` / `Request changes`).
  Never add a follow-up question. `Request changes` → capture feedback + forward constraints, apply
  Restart Routing, re-run affected steps through the self-review gate, ask again. `Start
  implementation` → proceed below.
- **`--yolo` mode**: skip the confirmation — once the self-review gate passes, proceed below.

**Spec/Plan Commit + Push Gate (mandatory, before Stage 03):** commit and push the approved Stage
02 artifacts with the auto message `docs(<artifact_id>): add spec, plan, and tasks` using
[../shared/commit.md](../shared/commit.md). Already-clean tree → skip per the conditional-commit
rule (success path). A failed commit/push here is a failure for the stage — stop with the exact
error; do not enter Stage 03 without this commit/push succeeding (or being a legitimate no-op).

Then discard Stage 02 interview context and invoke
[stage-03-implement-review.md](stage-03-implement-review.md) **immediately, in the same turn** —
no summary, no other questions, no waiting for another user message.