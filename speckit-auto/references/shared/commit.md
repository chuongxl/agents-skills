# Shared: Commit + Push Procedure (Provider-Agnostic)

Used by:
- Stage 04 (default mode, after human approval of the implementation)
- Stage 05 (`--yolo`, after `speckit-code-review` passes)
- The Stage 02 → Stage 03 handoff (github-speckit), to persist the approved spec/plan/tasks
  before implementation starts

The procedure is identical in all three call sites; only the commit message source differs —
Stage 04 asks the user, Stage 05 auto-generates `feat(<artifact_id>): <short summary from the spec
or Jira summary>`, and the Stage 02 → 03 handoff auto-generates
`docs(<artifact_id>): add spec, plan, and tasks` (see that stage file for the exact message).

`artifact_id` is provider-independent and always defined: the Jira issue key in `--issue` runs,
otherwise the artifact folder's prefix-slug (e.g. `007-user-export`). Never emit a literal
`<issue_id>` placeholder.

## Conditional Commit (Critical)

**Stage 03 may already have committed.** Implementer subagents (`subagent-driven-development`) and
`speckit.implement` both commit as they go, so the working tree is often clean by the time this
stage runs. An empty commit attempt exits non-zero, and global rule 19 would turn that into a false
pipeline failure at the very last step. Every commit below is therefore conditional.

1. Check what is actually uncommitted, in each repo before committing there:
   `git status --porcelain`
2. **Empty output → skip the commit for that repo** and log
   `already committed during Stage 03 (<n> commits on <branch>)`. This is a success path, not a
   failure. Verify the work is really there with `git log <base-branch>..HEAD --oneline`.
3. Non-empty → commit as below.

## With Submodules

If git submodules exist and were modified:

1. For each modified submodule whose status is dirty, commit **inside that submodule first**:
   - `git add -A`
   - `git commit -m "<commit-message>"`
2. Then, in the parent repo, commit the submodule pointer update and any parent changes. Re-check
   the parent's status **after** the submodule commits — a submodule commit dirties the parent
   pointer, so the parent may need a commit even when it looked clean a moment earlier:
   - `git add -A`
   - `git commit -m "<commit-message>"`

## Without Submodules

If no submodules were modified and the tree is dirty:

- `git add -A`
- `git commit -m "<commit-message>"`

## Branch Sync + Push (Required)

After the commit decision above (including the "already committed during Stage 03" success path),
sync and push the current feature branch to the remote:

1. Resolve the current branch:
   - `git branch --show-current`
2. Pull with rebase before pushing:
   - `git pull --rebase origin <branch>`
   - If this fails because the remote branch does not exist yet, continue to push (new branch path).
3. If rebase conflicts occur:
   - resolve conflicts in files
   - `git add <resolved-files>`
   - `git rebase --continue`
   - repeat until rebase completes
   - if conflicts cannot be resolved, stop and report the exact failure
4. Push to `origin`:
   - first push on a new branch: `git push -u origin <branch>`
   - subsequent pushes: `git push origin <branch>`
5. If push fails, stop and report the exact failure.

This stage must leave the implementation commit(s) available on the remote feature branch.

## Reporting

Report the resulting commits (hash + subject) and the pushed branch name. If nothing needed
committing, report the Stage 03 commits instead — never report "no commit" as a failure.

## Failure Handling

If a commit that was actually needed fails, stop and report the exact failure. A skipped commit on
an already-clean tree is **not** a failure and never stops the pipeline. A failed push is a failure
for this stage. A failed or unresolved rebase is also a failure for this stage.

## Scratch Must Already Be Ignored

`git add -A` here would otherwise sweep run scratch into the feature commit. Stage 01 guarantees
`.speckit/` (and `.superpowers/` in superpowers mode) are git-ignored — see
[scratch-hygiene.md](scratch-hygiene.md). The relocated `ticket.md` inside the artifact folder is
**not** scratch and is committed with the rest of the artifacts.
