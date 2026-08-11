# Stage 04 (superpowers): Human Manual Review + Commit (Default Mode Only)

Load this only in default mode after `speckit-code-review` returns `pass`.

## Human Manual Review Gate

1. AI provides a concise summary from the design spec + plan
   (`docs/superpowers/specs/<issue_id>-<short_title>-design.md`,
   `docs/superpowers/plans/<issue_id>-<short_title>.md`):
   - key use cases
   - expected usage scenarios
2. AI recommends the reviewer:
   - run the app
   - execute manual self-tests for those scenarios
3. Ask for the manual result:
   - `Approve implementation`
   - `Request changes`

## If Approved

1. Ask for the commit message.
2. If git submodules exist and were modified:
   - For each modified submodule, commit inside that submodule first:
     - `git add -A`
     - `git commit -m "<commit-message>"`
   - Then commit in the parent repo to record the submodule pointer update (and any parent changes):
     - `git add -A`
     - `git commit -m "<commit-message>"`
3. If no submodules were modified:
   - `git add -A`
   - `git commit -m "<commit-message>"`

## Optional PR Creation

`finishing-a-development-branch` may be invoked **only after** the commits above, and
**only** to push the branch and open a PR. Do not let it manage branch lifecycle, merge locally, or
clean up worktrees — no worktree exists in this pipeline.

## If Request Changes

1. Collect detailed human feedback.
2. Route the restart:
   - requirement change → `brainstorming`
   - solution/architecture change → `writing-plans` (structure)
   - task/detail change → `writing-plans` (task breakdown)
   - code-only change → direct file edits following the TDD cycle
3. Apply the fixes.
4. If code changed, invoke `speckit-code-review` again until `pass`.
5. Return to this gate and repeat until approved.
