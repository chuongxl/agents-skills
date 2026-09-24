# Stage 06: Clean / Commit / Push / PR / Complete (Provider-Agnostic)

Load right after Stage 05 hands off (whether it ran or was skipped). Final stage of the pipeline.

## 1. Clean (only if Stage 05 ran)

If Stage 05 was skipped, go straight to step 2. Otherwise, run the generated `verify-<app>`
skill's own Cleanup step now: tear down only what it launched (kill by tracked PID/handle, never
by process name). Evidence artifacts are never deleted by this step — they stay wherever
`verify-<app>` named them in its Evidence section. A cleanup that fails to find what it expects to
tear down is a warning, not a stop — log it and continue.

## 2. Commit verification artifacts (only if Stage 05 ran)

Commit the `.cursor/skills/verify-<app>/` skill files and feature-map changes only — never the
run's evidence/screenshots — via [../shared/commit.md](../shared/commit.md), call site "Stage 06
verification artifacts". The conditional-commit rule applies: if `create-verification-skill`'s
update-mode call in Stage 05 already produced no changes worth committing (rare, but possible if
the feature needed no map update), skip this commit and log why.

## 3. Mark spec completed

1. Update the active spec (`specs/<feature_folder>/spec.md`): set the status field to `completed`
   or add `Status: completed`.
2. Commit via [../shared/commit.md](../shared/commit.md), call site "Stage 06 spec completion".

## 4. Push

Run the Branch Sync + Push section of [../shared/commit.md](../shared/commit.md) for the parent
repo and every submodule with local commits ahead of its pushed base — this section already
handles submodules; do not re-derive push logic here.

## 5. PR creation (provider-agnostic, per repo)

For the parent repo, then for each submodule with commits ahead of its base branch (the same set
identified for push in step 4):

1. Detect the remote: `git -C <repo-or-submodule-path> remote get-url origin`.
2. Host is `github.com` → run `gh pr create` for that repo/submodule (title/body derived from the
   spec: title from the spec's title or `artifact_id`, body summarizing the spec's problem
   statement and this run's implementation commit(s)). Treat "a pull request for branch `<branch>`
   already exists" as **success**, not an error — idempotent.
3. Any other host, or `gh` not installed/not authenticated → report `PR not created for <repo>:
   <reason>` and continue. Non-blocking: one repo's failure never stops another repo's PR attempt
   or the rest of this stage.
4. Record the outcome per repo (`created` / `already existed` / `skipped: <reason>`) for the final
   report below.

## Failure Handling

- Verification-artifact commit or spec-completion commit failing when one was actually needed, a
  failed push, or an unresolved rebase → stop and report the exact error (same philosophy as
  [../shared/commit.md](../shared/commit.md)); do not claim pipeline success without the
  completion commit.
- PR creation failures are per-repo non-blocking, per step 5 above — never a stage-level stop.

## Final Report

At completion report: resolved provider, `speckit-code-review` final status (`pass`),
verification outcome (`verification: skipped` or `verification: passed`, plus
`investigate_loops: N` if Stage 05 looped at least once), the implementation commit(s) (from Stage
04), the verification-artifact commit (if any), the spec completion commit hash, pushed branches,
and per-repo PR outcomes. In `--issue` mode, update the execution report first (Stage 01 §7).
