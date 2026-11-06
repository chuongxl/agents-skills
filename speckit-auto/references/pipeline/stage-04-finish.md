# Stage 04: Human Review / Implementation Commit (Provider-Agnostic)

Load after `speckit-code-review` returns `pass`. Two paths: **default mode** (human review gate is
mandatory, never skipped) and **YOLO** (no human interactions). Both paths end at the same place:
the implementation is committed and pushed, and control passes to Stage 05.

At actual entry or re-entry emit `{type: "stage_started", stage: "04-finish"}` using the shared
JSON stdin invocation, not on context-only resume.

## Default Mode — Human Manual Review Gate

1. Present a concise summary from spec + plan: key use cases, expected usage scenarios.
2. Recommend the reviewer run the app / execute manual self-tests for those scenarios.
3. Ask via the host ask tool: `Approve implementation` / `Request changes`.
   Immediately before asking emit `gate_waiting` with `stage: "04-finish"` and
   `gate: "implementation-approval"`; immediately after either response emit `gate_answered`
   with the same stage/gate and no answer text.

### If Request Changes

1. Collect the detailed human feedback.
2. Route the restart to the earliest affected step: requirement change → `specify` /
   `brainstorming`; solution/architecture change → `plan` / `writing-plans` (structure);
   task/detail change → `tasks` / `writing-plans` (task breakdown); code-only change →
   implementation step / direct edits under TDD.
3. **Restart through, not just at, that step**: re-run every downstream Stage 02 step in order so
   no derived artifact is left stale, re-run the Stage 02 mandatory self-review gate, commit + push
   the regenerated Stage 02 artifacts via the Spec/Plan Commit Gate (Stage 02), then re-enter the
   **full** Stage 03 flow (PHASE 1 + PHASE 2) until `status = pass` — the no-stop rules apply
   again for that re-entry.
4. Return to this gate and repeat until approved.

Request changes is an answered gate, not a `run_failed`. Feedback-detail questions emit
`question_waiting` for `04-finish` immediately before the ask and `stage_started` for `04-finish`
after the response. Start the earliest restarted stage with its `stage_started` event.
Do not finish abandoned Stage 04 work or mark the run terminal while revising.

### If Approved

Ask for the commit message, then run the commit + push procedure in
[../shared/commit.md](../shared/commit.md) with that message.
Bracket the commit-message ask with `question_waiting` for `04-finish`, using "Provide a commit
message", and `stage_started` for `04-finish` immediately after the response. Do not emit the
message itself.

## YOLO Path

Skip every human review/approval interaction. Auto-generate the commit message
`feat(<artifact_id>): <short summary from the spec or Jira summary>`, then run the commit + push
procedure in [../shared/commit.md](../shared/commit.md) with that message.
Emit no human waiting/answered events for this skipped review or commit-message interaction.

## Handoff (both modes)

After the implementation commit succeeded (or was skipped because nothing needed committing — see
[../shared/commit.md](../shared/commit.md)'s conditional-commit rule), emit
`{type: "stage_finished", stage: "04-finish"}`, then load
[stage-05-verification.md](stage-05-verification.md) and enter Stage 05 in the same turn. Stage 05
(conditional verification) runs next and hands off to Stage 06, which owns cleanup, spec
completion, the final push, the pull request, and the terminal `run_completed`. Stage 04 never
emits `run_completed`.

The implementation is already pushed at this point, before any verification. That is deliberate:
it has passed `speckit-code-review` and human approval, and nothing is *published* (no PR) until
Stage 06.

## Failure Handling

- A commit that was actually needed failing, a failed push, or an unresolved rebase → stop and
  report (shared/commit.md).
- On these hard exits emit `run_failed` with `reason.code: "git_error"`, before reporting. Do not
  duplicate a terminal event already emitted by shared/commit.md. On an event write error, stop
  and never emit `run_completed` or claim success.

## Report

At this checkpoint report: resolved provider, `speckit-code-review` final status (`pass`), the
implementation commit(s) (hash + subject) and pushed branch, then note Stage 05 is next.
