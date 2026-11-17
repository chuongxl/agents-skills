# Speckit Auto PR-fix mode

## Goal

Add a generic `/speckit-auto --pr-fix <PR URL>` path that fixes an existing pull request
without changing its identity or creating another pull request. Manual invocations and callers
that provide an existing worktree use the same path.

## Scope

- Keep the existing provider selection and pipeline stages. Route their behavior for PR fixes
  rather than starting a separate feature pipeline.
- Preserve the existing feature and Jira workflows when `--pr-fix` is absent.
- Support an existing linked worktree or create a new isolated worktree from the PR head.
- Review and verify the requested fix and push it to the existing PR head.

## PR identity and worktree

`--pr-fix` requires an absolute pull request URL and a fix request. Resolve the repository,
PR base, head repository, head branch, and current head SHA from the hosting service. Validate
that the PR is open and that its head can be fetched and pushed before making changes.
Reject missing or ambiguous identity rather than guessing a destination.

If the invocation provides a worktree and branch, verify that they belong to the intended
repository and are based on the resolved PR head. Reuse them without switching or renaming the
branch or creating another worktree. If no worktree is provided, create a linked worktree and
local branch from the fetched PR head. Do not disturb other worktrees or uncommitted changes.
Handle a PR whose head belongs to a fork by resolving the head repository explicitly; fail
clearly if it cannot be accessed or pushed.

Capture the PR head SHA at intake. Before pushing, fetch the head again and ensure the update
is a fast-forward from the current remote head. If it has diverged, stop with an actionable
failure instead of force-pushing or discarding work. Push the local HEAD to the resolved PR
head branch. Never create a PR in this mode.

## Pipeline routing

Stage 01 collects the PR and fix request, resolves the worktree, and initializes run events
with the supplied run ID. It does not derive a new feature branch or spec folder.

Stage 02 identifies a relevant existing spec using the PR's changes and feature identity.
Reuse that spec when it matches the PR. Update its requirements, plan, and tasks through the
selected provider only when the fix request changes those requirements; do not generate a
new feature spec for a maintenance fix. If no matching spec exists, retain the PR description,
fix request, and existing behavior as the review basis.

Stage 03 implements the fix and tests it. When a relevant spec exists, invoke
`speckit-code-review` against the full PR change set and the fix. Without a spec, review the
same scope directly against the PR and request, including correctness, security, and regression
coverage. Do not fabricate a spec or claim a spec-based review passed. Resolve blocking
findings before continuing.

Stage 04 preserves the existing approval behavior and commits only this run's changes.
Stage 05 runs configured verification against the fix; report unavailable verification
honestly under the existing mode rules. Stage 06 pushes to the existing PR head, without
creating another PR or marking an unrelated spec complete.

Existing default-mode approval gates and YOLO behavior remain applicable. Skipped stages or
gates must not be reported as completed. Run events retain the existing schema and run ID;
emit `run_completed` only after required checks and a successful push, or `run_failed` for
a terminal failure. A successful no-change result must be distinguished from an unverified
or failed fix.

## Checks and formatting

Run the relevant existing tests and project checks for the fix. Check formatting on changed
files and report repository-wide formatting failures separately when they predate and are
unrelated to the fix. Do not change unrelated files or report a failed required check as
passed. Preserve any pre-existing user edits.

## Verification

Test both providers and default/YOLO modes using scenarios for:

- an existing worktree and branch, and a manual run without either;
- an existing relevant spec, a requirement-changing fix, and a PR with no matching spec;
- an already checked-out head branch, a forked head, inaccessible or closed PRs, and a
  remote head that moves before push;
- preservation of unrelated edits, changed-file formatting, and baseline formatting failures;
- review, verification, commit, push, and run-event success and failure paths;
- unchanged behavior for feature and Jira invocations without `--pr-fix`.

The skill is instruction-driven, so verify its behavior with the repository's skill validation
tools and documented end-to-end agent scenarios, not only text-matching tests.
