# Stage 04: Human Review / Commit / Spec Completion (Provider-Agnostic)

Load after `speckit-code-review` returns `pass`. Two paths: **default mode** (human review gate is
mandatory, never skipped) and **YOLO** (no human interactions).

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

## Mark Spec Completed + Follow-up Commit (both modes)

After the implementation commit succeeded:

1. Update the active spec (`specs/<feature_folder>/spec.md`): set the status field to `completed`
   or add `Status: completed`.
2. Commit the status update: `git add <spec-path>` and
   `git commit -m "chore(spec): mark <artifact_id> completed"`.
   Use the shared conditional-commit rule if the spec is already completed and clean.
3. After the completion commit, sync and push the feature branch again per shared/commit.md.
   Verify that the completion commit is on the remote branch. Neither the earlier implementation
   push nor a non-blocking finishing skill substitutes for this required final push.

## Final Step — `finishing-a-development-branch` (superpowers only)

**Runs only after ALL of the above have succeeded** (human approval or YOLO auto-approve,
implementation commit/push, spec completion commit). Never called in Stage 03, never called
before approval, never called to commit or push code.

Invoke `skill finishing-a-development-branch` with no prompt. It handles any final branch
lifecycle actions (e.g. opening a PR in default mode). If the skill is not available or fails,
log the error and continue — this step is non-blocking and does not affect pipeline success.
Bracket any pipeline-owned lifecycle question with the shared question events in default mode;
YOLO remains non-interactive. Once an actual absolute HTTPS PR URL is confirmed from creation
or a verified existing PR lookup, emit `{type: "pr_opened", pr_url: <confirmed URL>}`.
Pass the URL as data via an argument vector to the Node wrapper. Never interpolate it into
code, emit a placeholder, infer a PR from a planned action, or repeat an already-recorded URL
on resume. This applies to either provider whenever a PR is actually opened. No PR is required
to complete the pipeline, and a failed optional PR action alone is not a failed run.

## Failure Handling

- Spec status update or completion commit fails → stop and report the exact error; do not claim
  pipeline success without the completion commit.
- A commit that was actually needed failing, a failed push, or an unresolved rebase → stop and
  report (shared/commit.md).
- On these hard exits emit `run_failed` with `reason.code: "git_error"` for git failures or
  `crashed` for spec-file write failures, before reporting. Do not duplicate a terminal event
  already emitted by shared/commit.md. On an event write error, stop and never emit
  `run_completed` or claim success.

## Final Report

At completion report: resolved provider, `speckit-code-review` final status (`pass`), the
implementation commit(s) (hash + subject) and pushed branch, and the spec completion commit hash.
In `--issue` mode, update the execution report first (Stage 01 §7).
Only after all required commits, the spec completion push, and execution-report updates
succeed, emit `{type: "stage_finished", stage: "04-finish"}`, then `{type: "run_completed"}`.
Check each write before the next action and before the final success report.