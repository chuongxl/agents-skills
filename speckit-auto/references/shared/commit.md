# Shared: Commit + Push Procedure (Provider-Agnostic)

Used by: the Stage 02 → Stage 03 spec/plan commit gate, Stage 04 human-review commit (default
mode), and the Stage 04 YOLO auto-commit. The procedure is identical; only the commit message
source differs:

| Call site | Message |
|-----------|---------|
| Stage 02 → 03 gate | auto: `docs(<artifact_id>): add spec, plan, and tasks` |
| Stage 04 default | asked from the user |
| Stage 04 YOLO | auto: `feat(<artifact_id>): <short summary from the spec or Jira summary>` |

`artifact_id` is always defined: the Jira issue key in `--issue` runs, otherwise the artifact
folder's prefix-slug (e.g. `007-user-export`). Never emit a literal `<issue_id>` placeholder.

## Conditional Commit (Critical)

Implementers commit as they go, so the tree is often already clean by the time this runs; an
empty commit attempt exits non-zero and would produce a false failure. Every commit is therefore
conditional:

1. Check `git status --porcelain` in each repo before committing there.
2. **Empty output → skip that repo's commit** and log `already committed during Stage 03 (<n>
   commits on <branch>)`; verify the work with `git log <base-branch>..HEAD --oneline`. This is a
   success path, not a failure.
3. Non-empty → commit as below.

## With Submodules

If modified submodules exist: commit inside each dirty submodule first (`git add -A` →
`git commit -m "<message>"`), then commit the parent pointer update and any parent changes. Re-check
the parent status **after** the submodule commits — a submodule commit dirties the parent pointer,
so the parent may need a commit even when it looked clean moments earlier.

## Without Submodules

`git add -A` → `git commit -m "<message>"`.

## Branch Sync + Push (Required)

After the commit decision (including the already-clean success path):

1. `git pull --rebase origin <branch>` — if the remote branch does not exist yet, continue to push
   (new branch path). On conflicts: resolve, `git add <files>`, `git rebase --continue`, repeat; if
   unresolvable, stop and report.
2. Push: first push `git push -u origin <branch>`; subsequent `git push origin <branch>`.
3. Push failure → stop and report the exact error.

The stage must leave the implementation commit(s) available on the remote feature branch.

## Reporting and Failure Handling

Report resulting commits (hash + subject) and the pushed branch. If nothing needed committing,
report the Stage 03 commits instead — never report "no commit" as a failure. A failed commit that
was actually needed, a failed push, or an unresolved rebase is a failure for the stage; a skipped
commit on an already-clean tree is not.

## Scratch Must Already Be Ignored

`git add -A` would otherwise sweep run scratch into the feature commit. The relocated
`ticket.md` inside the artifact folder is **not** scratch and is committed with the artifacts.