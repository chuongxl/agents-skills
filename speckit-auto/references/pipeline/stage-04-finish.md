# Stage 04: Human Review / Implementation Commit (Provider-Agnostic)

Load after `speckit-code-review` returns `pass`. Two paths: **default mode** (human review gate is
mandatory, never skipped) and **YOLO** (no human interactions). Both paths end at the same place:
the implementation is committed, and control passes to Stage 05.

## Default Mode — Human Manual Review Gate

1. Present a concise summary from spec + plan: key use cases, expected usage scenarios.
2. Recommend the reviewer run the app / execute manual self-tests for those scenarios.
3. Ask via the host ask tool: `Approve implementation` / `Request changes`.

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

### If Approved

Ask for the commit message, then run the commit + push procedure in
[../shared/commit.md](../shared/commit.md) with that message.

## YOLO Path

Skip every human review/approval interaction. Auto-generate the commit message
`feat(<artifact_id>): <short summary from the spec or Jira summary>`, then run the commit + push
procedure in [../shared/commit.md](../shared/commit.md) with that message.

## Handoff (both modes)

After the implementation commit succeeded (or was skipped because nothing needed committing — see
[../shared/commit.md](../shared/commit.md)'s conditional-commit rule), load
[stage-05-verification.md](stage-05-verification.md) and enter Stage 05 in the same turn. Stage 05
owns everything from here: verification (conditional), cleanup, marking the spec completed,
pushing, and PR creation.

## Failure Handling

- A commit that was actually needed failing, a failed push, or an unresolved rebase → stop and
  report (shared/commit.md).

## Report

At this checkpoint report: resolved provider, `speckit-code-review` final status (`pass`), the
implementation commit(s) (hash + subject) and pushed branch, then note Stage 05 is next.
