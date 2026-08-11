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
