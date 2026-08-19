# Stage 04: Human Review / Commit / Spec Completion (Provider-Agnostic)

Load after `speckit-code-review` returns `pass`. Two paths: **default mode** (human review gate is
mandatory, never skipped) and **YOLO** (no human interactions).

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

## Mark Spec Completed + Follow-up Commit (both modes)

After the implementation commit succeeded:

1. Update the active spec (`specs/<feature_folder>/spec.md`): set the status field to `completed`
   or add `Status: completed`.
2. Commit the status update: `git add <spec-path>` and
   `git commit -m "chore(spec): mark <artifact_id> completed"`.

## Final Step — `finishing-a-development-branch` (superpowers only)

**Runs only after ALL of the above have succeeded** (human approval or YOLO auto-approve,
implementation commit/push, spec completion commit). Never called in Stage 03, never called
before approval, never called to commit or push code.

Invoke `skill finishing-a-development-branch` with no prompt. It handles any final branch
lifecycle actions (e.g. opening a PR in default mode). If the skill is not available or fails,
log the error and continue — this step is non-blocking and does not affect pipeline success.

## Failure Handling

- Spec status update or completion commit fails → stop and report the exact error; do not claim
  pipeline success without the completion commit.
- A commit that was actually needed failing, a failed push, or an unresolved rebase → stop and
  report (shared/commit.md).

## Final Report

At completion report: resolved provider, `speckit-code-review` final status (`pass`), the
implementation commit(s) (hash + subject) and pushed branch, and the spec completion commit hash.
In `--issue` mode, update the execution report first (Stage 01 section 8).