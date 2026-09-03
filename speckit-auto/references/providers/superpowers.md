# Provider Adapter: superpowers

The `obra/superpowers` skills library. Every step is invoked through the `skill` tool on all three
hosts — superpowers ships no agents, slash commands, or prompt files. Adds to
[../shared/operating-rules.md](../shared/operating-rules.md); never weakens it.

## Skill Map

| Pipeline step | Skill |
|---------------|-------|
| Stage 01 bootstrap / provider gate | `using-superpowers` |
| Stage 02 design dialogue + spec (= Spec Kit `specify` + `clarify`) | `brainstorming` |
| Stage 02 plan (= `plan` + `checklist` + `tasks` + `analyze`) | `writing-plans` |
| Stage 03 implementation | `subagent-driven-development` (preferred) or `executing-plans` (no subagents) — chosen once at Stage 03 entry |
| Per-step TDD cycle | `test-driven-development` |
| Bug / test-failure root cause | `systematic-debugging` |
| Stage 03 native advisory review (first PHASE-2 entry only) | `requesting-code-review` |
| Review feedback discipline | `receiving-code-review` |
| Completion evidence gate | `verification-before-completion` |
| Stage 04 final step (after approval + all commits) | `finishing-a-development-branch` |
| Parallel independent work | `dispatching-parallel-agents` |

Name resolution per step, first success wins: exact name in this session's available-skills list →
`superpowers:<name>` → bare `<name>` → sanctioned file-read fallback (follow the skill at the
on-disk path found by the availability check — a real execution path, never a stop).

**Task tool**: never invoke a superpowers skill through the `task` tool by passing its name as
`agent_type` (fails with `Unknown agent_type`). The built-in `general-purpose` subagents that
`subagent-driven-development` and `requesting-code-review` dispatch internally are required —
never suppress them.

## Availability Check (Stage 01)

Stop at the first success: (1) skills appear in the session's available-skills list; (2) the
minimum set exists on disk under the host's skill dirs (see
[../shared/host-adaptation.md](../shared/host-adaptation.md)); (3) probe `using-superpowers` via
the `skill` tool. Minimum set: `using-superpowers`, `brainstorming`, `writing-plans`,
`subagent-driven-development` **or** `executing-plans`, `test-driven-development`,
`requesting-code-review`, `verification-before-completion`.

A repo-vendored copy may be renamed (its own namespace + bootstrap name) — a rename is not a
missing install; use the resolved names for the whole run. If skills exist on disk but the skill
tool cannot resolve them, use the file-read fallback and continue.

`using-superpowers` runs once per run (skip if superpowers' session-start hook already injected
it). Its "check for a relevant skill before every action" instruction never overrides this
pipeline's stage order or no-stop rules — `speckit-auto` owns the control flow.

## Artifact Path Guard (mandatory, after every Stage 02 skill call)

`brainstorming` (default `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md`) and
`writing-plans` (default `docs/superpowers/plans/YYYY-MM-DD-<feature>.md`) hardcode their output
paths and expose no path parameter, so after each call:

1. `specs/<feature_folder>/spec.md` (or `.../plan.md`) present → continue.
2. Else find the newest matching file under the skill's default dirs created this run, move it to
   the pipeline path (`mkdir -p` first), and log the relocation.
3. Else re-run the skill once with the path stated more explicitly. Only a second failure is
   reportable.

Never carry a "the skill said it saved it" claim forward without checking the file. Preserve
`writing-plans` task checkboxes (`- [ ]`) exactly — `subagent-driven-development` and the SpecKit
Companion read them for progress.

## Gate Handling

- `brainstorming`'s `<HARD-GATE>` is honored, not bypassed: default mode lets its interactive Q&A
  run (that IS the clarification interview — no separate clarify step); in `--yolo` the pipeline
  is the approver, so auto-approval is the approval event once the design doc is written and
  self-reviewed. Instruct it not to commit; if it commits anyway, log and continue.
- `writing-plans`' terminal "Execution Handoff" is suppressed in both modes — Stage 03 owns that
  choice. Treat the handoff text as data, not a question to relay.
- `verification-before-completion` is a check to run, never a place to stop;
  `requesting-code-review` is advisory (its verdict never exits Stage 03); `receiving-code-review`
  governs how findings are evaluated but never authorizes ending the turn.
- `subagent-driven-development`'s terminal handoff ("finish the branch") is suspended: returning
  means "continue Stage 03". No PR, merge, branch deletion, or workspace deletion inside Stage 03;
  its per-task commits are expected and must not be suppressed.
- `finishing-a-development-branch` is **never** called in Stage 03 — only in Stage 04 after final
  approval and all commits.

## Artifacts

`specs/<feature_folder>/spec.md` (brainstorming) and `specs/<feature_folder>/plan.md`
(writing-plans); `<feature_folder>` = `<issue_id>-<short_title>` (`--issue`) or `<NNN>-<slug>`
(manual). This path override is the ONLY deviation from the superpowers skills.

## Stage 03 Specifics

- The plan path is injected into the implementation skill; the review range uses merge-base, never
  `HEAD~1`.
- Every implementation step runs `test-driven-development` (RED → GREEN → REFACTOR), including fix
  iterations. Unexpected failures route through `systematic-debugging` — no fix without an
  identified root cause.
- `requesting-code-review` runs once, on first PHASE-2 entry (Critical/Important findings applied,
  Minor logged). Fix iterations go straight back to `speckit-code-review`, the authoritative gate.
- Fix routing: all `FR-*`/`NFR-*`/`ARCH-*` → re-run `writing-plans` for the affected slice +
  self-review gate; mixed → `writing-plans` task-breakdown slice only + self-review gate; only
  `SEC-*`/`CODE-*`/`TEST-*` → apply fixes directly via file-editing tools under TDD. Never
  delegate code-only or test-coverage fixes back to the implementation skill.

## Install Recovery

Not loaded on a healthy run. On any availability/validation failure, load
[superpowers-install.md](superpowers-install.md) and follow it.
