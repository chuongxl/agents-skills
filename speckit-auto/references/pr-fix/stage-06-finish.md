# PR fix: Stage 06 update and completion

Perform cleanup and commit verification artifacts as in the shared Stage 06 steps 1–2, scoped to
this run. Never mark an unrelated spec completed. Default mode asks the existing `pr-publish` gate
to authorize updating the resolved existing PR head, showing its URL, repository, branch and
commits; declining stops without a push or completion event and emits `run_failed` with
`policy_blocked`. Bracket the ask with the normal `pr-publish` gate events. YOLO authorizes the
update without a wait. Never call `gh pr create` or fan out new PRs in this mode.

Immediately before the push, re-query the open PR and verify its head repository and ref still
match intake. Fetch that exact head into a private temporary ref, confirm the fetched SHA matches
the API head, and require it to be an ancestor of local HEAD. If it is not, stop with `git_error`;
do not overwrite remote work. Push `HEAD` to `refs/heads/<pr_head_branch>` at the authenticated
resolved head-repository URL using an ordinary non-force push, then fetch again and verify its
SHA equals local HEAD, including a no-change run. A concurrent update or rejected push is a
terminal `git_error`, never a success. Use argument-vector commands and do not print authenticated
URLs or credentials. On failure emit `run_failed` as directed by shared/commit.md and do not emit
completion.

If this run pushed a new commit, emit `pr_opened` with the confirmed existing PR URL after push
verification, unless that URL was already recorded on resume. This existing event also records
delivery evidence; it does not mean a new PR was created. For a verified no-change run, do not
emit `pr_opened` or claim delivery. Report the existing PR URL, actual review type, checks,
verification outcome and pushed SHA; distinguish a verified no-change result. Emit `stage_finished`
then `run_completed` only after the required push verification succeeds.
