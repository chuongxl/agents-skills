# Stage 04 (superpowers): Human Manual Review + Commit (Default Mode Only)

Load this only in default mode after `speckit-code-review` returns `pass`.

## Human Manual Review Gate

1. AI provides a concise summary from the design spec + plan
   (`specs/<feature_folder>/spec.md`,
   `specs/<feature_folder>/plan.md`):
   - key use cases
   - expected usage scenarios
2. AI recommends the reviewer:
   - run the app
   - execute manual self-tests for those scenarios
3. Ask for the manual result:
   - `Approve implementation`
   - `Request changes`

## If Approved

**Stage 03 usually already committed.** `subagent-driven-development`'s implementer subagents
commit after each task, so the working tree is often clean by the time this stage runs. An empty
commit attempt exits non-zero, and global rule 19 would turn that into a false pipeline failure at
the very last step. So every commit below is conditional.

1. Ask for the commit message.
2. Check what is actually uncommitted, in each repo before committing there:
   - `git status --porcelain`
   - **Empty output → skip the commit for that repo and log
     `already committed during Stage 03 (<n> commits on <branch>)`.** This is a success path, not
     a failure. Verify with `git log <base-branch>..HEAD --oneline` that the work is really there.
   - Non-empty → commit as below.
3. If git submodules exist and were modified:
   - For each modified submodule, commit inside that submodule first (when its status is dirty):
     - `git add -A`
     - `git commit -m "<commit-message>"`
   - Then, in the parent repo, commit the submodule pointer update and any parent changes. Check
     the parent's status **after** the submodule commits — a submodule commit dirties the parent
     pointer, so the parent may need a commit even when it looked clean a moment earlier:
     - `git add -A`
     - `git commit -m "<commit-message>"`
4. If no submodules were modified and the tree is dirty:
   - `git add -A`
   - `git commit -m "<commit-message>"`
5. Report the resulting commits (hash + subject). If nothing needed committing, report the Stage 03
   commits instead — never report "no commit" as a failure.

Do not `git add -A` review scratch: `.speckit/` (review detail files and state) and `.superpowers/`
(the implementation ledger and briefs) must be ignored before this point — Stage 01 ensures that.

## Optional PR Creation

`finishing-a-development-branch` may be invoked **only after** the commits above, and
**only** to push the branch and open a PR. Do not let it manage branch lifecycle, merge locally, or
clean up worktrees — no worktree exists in this pipeline.

## If Request Changes

1. Collect detailed human feedback.
2. Route the restart to the earliest affected step:
   - requirement change → `brainstorming`
   - solution/architecture change → `writing-plans` (structure)
   - task/detail change → `writing-plans` (task breakdown)
   - code-only change → direct file edits following the TDD cycle
3. **Restart through, not just at, that step**: if `brainstorming` re-runs, `writing-plans` must
   re-run after it, and the Stage 02 mandatory self-review gate must pass again — no derived
   artifact may be left stale.
4. Then re-enter the **full** Stage 03 flow (implementation + verification loop, then R0 native
   review, then the `speckit-code-review` loop) until `status = pass`. Stage 03's no-stop rules
   apply again for that re-entry.
5. Return to this gate and repeat until approved.
