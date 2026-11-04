# Stage 06: Clean / Commit / Push / PR / Complete (Provider-Agnostic)

Load right after Stage 05 hands off (whether it ran or was skipped). Final stage of the pipeline.

At actual entry or re-entry emit `{type: "stage_started", stage: "06-finish"}` using the shared
JSON stdin invocation, not on context-only resume.

## 1. Clean (only if Stage 05 launched something)

If Stage 05 was skipped, go straight to step 2. Otherwise, run the generated `verify-<app>`
skill's own Cleanup step now: tear down only what it launched (kill by tracked PID/handle, never
by process name). Evidence artifacts are never deleted by this step — they stay wherever
`verify-<app>` named them in its Evidence section. A cleanup that fails to find what it expects to
tear down is a warning, not a stop — log it and continue.

## 2. Commit verification artifacts (only if Stage 05 ran)

Commit the `.cursor/skills/verify-<app>/` skill files and feature-map changes only — never the
run's evidence/screenshots — via [../shared/commit.md](../shared/commit.md), call site "Stage 06
verification artifacts". The conditional-commit rule applies: if the update-mode call in Stage 05
produced no changes worth committing, skip this commit and log why.

## 3. Mark Spec Completed + Follow-up Commit (both modes)

After verification (or its skip) is settled:

1. Update the active spec (`specs/<feature_folder>/spec.md`): set the status field to `completed`
   or add `Status: completed`.
2. Commit the status update: `git add <spec-path>` and
   `git commit -m "chore(spec): mark <artifact_id> completed"`.
   Use the shared conditional-commit rule if the spec is already completed and clean.
3. After the completion commit, sync and push the feature branch again per shared/commit.md.
   Verify that the completion commit is on the remote branch. Neither the earlier implementation
   push nor the later draft-PR step substitutes for this required final push.

Submodules: the push in item 3 covers the parent and every submodule with local commits ahead of
its pushed base, per the Branch Sync + Push section of
[../shared/commit.md](../shared/commit.md).

## 4. Open the Pull Request (both providers)

**Runs only after ALL of the above have succeeded** (human approval or YOLO auto-approve,
implementation commit/push, verification when enabled, spec completion commit and its verified
push). Never run in Stage 03,
never before approval, never to commit or push code. The step is non-blocking: a failure is
logged and does not affect pipeline success. No PR is required to complete the pipeline.

### Authorization

Opening a PR publishes the branch and its diff to everyone with repository access, notifies
watchers, and triggers CI and bots. The implementation-approval gate covers the implementation
only — it is not an authorization to publish.

- **Default mode** — ask once, after the spec-completion push and before any PR command.
  Immediately before the ask emit `gate_waiting` with `stage: "06-finish"` and
  `gate: "pr-publish"`; immediately after the response emit `gate_answered` with the same
  stage/gate and no answer text. Show the branch, the base branch, the title, and the full body
  that would be published. Options: `Open draft PR` / `Skip PR`.
  `Skip PR` → log the skip, create nothing, emit no `pr_opened`, and continue; the pipeline still
  succeeds.
- **YOLO mode** — create the draft PR with no wait. `--yolo` is the explicit authorization for
  this: say so in the invocation output and in the Final Report.

### Procedure (both providers, both modes)

1. Resolve the repository default branch (`gh repo view --json defaultBranchRef`). It is not
   necessarily the Stage 01 base branch and not necessarily `main`.
2. Skip, and log why, when `gh` is missing or unauthenticated, the branch has no remote, or the
   branch is the repository default branch.
3. Look up an existing PR for the pushed branch (`gh pr list --head <branch> --state open
   --json url`). If one exists, reuse its URL and do not create another.
4. Otherwise create a **draft** PR against the resolved default branch with
   `gh pr create --draft --base <default> --head <branch> --title <t> --body-file <f>`. Title:
   the implementation commit subject. Body: a short summary from the spec (what changed and why),
   the `speckit-code-review` status, the Jira issue link in `--issue` mode, and any known
   limits the spec or plan records. Write the body to a file under the run's temp directory.
   Never merge, never push to the default branch, never force-push.
   - Draft is deliberate, and its limits are narrow: it blocks auto-merge and keeps the PR out of
     the ready-for-review queue. It does **not** prevent publication — `pull_request` workflows
     still run on `opened` for draft PRs, and watchers are still notified.

Once an actual absolute HTTPS PR URL is confirmed from creation or a verified existing PR
lookup, emit `{type: "pr_opened", pr_url: <confirmed URL>}`. Pass the URL as data via an argument
vector to the Node wrapper. Never interpolate it into code, emit a placeholder, infer a PR from a
planned action, or repeat an already-recorded URL on resume. Report the PR URL in the Final
Report; report a `Skip PR` decision as "no PR opened".

### Submodules

After the parent repo, repeat the Procedure for each submodule with commits ahead of its base
branch (the same set pushed in step 3), using that submodule's own remote
(`git -C <path> remote get-url origin`). A non-GitHub host, or `gh` missing/unauthenticated,
reports `PR not created for <repo>: <reason>` and continues. Each repo is authorized by the same
single `pr-publish` answer (default mode: show every repo's branch/base/title/body in that one
ask). One repo's failure never stops another's attempt. Record the outcome per repo
(`created` / `already existed` / `skipped: <reason>`).

## Failure Handling

- Spec status update or completion commit fails → stop and report the exact error; do not claim
  pipeline success without the completion commit.
- A verification-artifact commit that was actually needed failing, a failed push, or an unresolved
  rebase → stop and report (shared/commit.md).
- On these hard exits emit `run_failed` with `reason.code: "git_error"` for git failures or
  `crashed` for spec-file write failures, before reporting. Do not duplicate a terminal event
  already emitted by shared/commit.md. On an event write error, stop and never emit
  `run_completed` or claim success.
- PR creation failures are per-repo non-blocking — never a stage-level stop.

## Final Report

At completion report: resolved provider, `speckit-code-review` final status (`pass`),
verification outcome (`verification: skipped` or `verification: passed`, plus
`investigate_loops: N` if Stage 05 looped at least once; in YOLO, `passed` means auto-approved),
the implementation commit(s) (from Stage 04), the verification-artifact commit (if any), the spec
completion commit hash, pushed branches, and per-repo PR outcomes (URL, "already existed", or "no
PR opened" when the human skipped the `pr-publish` gate or creation failed). In YOLO mode, state
that the PR was opened under `--yolo` authorization rather than a human `pr-publish` approval.
In `--issue` mode, update the execution report first (Stage 01 §7).
Only after all required commits, the spec completion push, and execution-report updates
succeed, emit `{type: "stage_finished", stage: "06-finish"}`, then `{type: "run_completed"}`.
Check each write before the next action and before the final success report.
