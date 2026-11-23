# PR fix: Stage 06 update and completion

Perform cleanup and commit verification artifacts as in the shared Stage 06 steps 1–2, scoped to
this run. Never mark an unrelated spec completed. Default mode asks the existing `pr-publish` gate
to authorize updating the resolved existing PR head, showing its URL, repository, branch and
commits, marking any commit that is neither in the fetched PR head nor made by this run as extra; declining stops without a push or completion event and emits `run_failed` with
`policy_blocked`. Bracket the ask with the normal `pr-publish` gate events. YOLO authorizes the
update without a wait. Never call `gh pr create` or fan out new PRs in this mode.

Immediately before the push, re-query the open PR and verify its head repository and ref still
match intake. Verify that unrelated initial paths still have their original index and worktree
contents; if not, stop and report the paths without printing their contents. Fetch that exact head
into a private temporary ref, confirm the fetched SHA matches
the API head, and require it to be an ancestor of local HEAD. If it is not, stop with `git_error`;
do not overwrite remote work. Push `HEAD` to `refs/heads/<pr_head_branch>` at the authenticated
resolved head-repository URL using an ordinary non-force push, then fetch again and verify its
SHA equals local HEAD, including a no-change run. A concurrent update or rejected push is a
terminal `git_error`, never a success. Use argument-vector commands and do not print authenticated
URLs or credentials. On failure emit `run_failed` as directed by shared/commit.md and do not emit
completion.

If this run pushed a new commit, emit `pr_updated` with the confirmed existing PR URL after push
verification, unless it was already recorded on resume. Never emit `pr_opened` here. For a
verified no-change run, emit neither and do not claim delivery. Report the existing PR URL, actual review type, checks,
verification outcome and pushed SHA; distinguish a verified no-change result. Emit `stage_finished`
then `run_completed` only after the required push verification succeeds.
