# Stage 04: Human Manual Review + Commit (Default Mode Only)

Load this only in default mode after `speckit-code-review` returns `pass`.

## Human Manual Review Gate

1. AI provides concise summary from `spec.md` + `plan.md`:
   - key use cases
   - expected usage scenarios
2. AI recommends reviewer:
   - run the app
   - execute manual self-tests for those scenarios
3. Ask manual result:
   - `Approve implementation`
   - `Request changes`

## If Approved

1. Ask for commit message.
2. If git submodules exist and were modified:
   - For each modified submodule, run commit in that submodule first:
     - `git add -A`
     - `git commit -m "<commit-message>"`
   - Then commit in parent repo to record submodule pointer update (and any parent changes):
     - `git add -A`
     - `git commit -m "<commit-message>"`
3. If no modified submodules, keep current behavior:
   - `git add -A`
   - `git commit -m "<commit-message>"`

## If Request Changes

1. Collect detailed human feedback.
2. Route the restart to the earliest affected step:
   - requirement change → repo `speckit.specify`
   - solution change → repo `speckit.plan`
   - task/detail change → repo `speckit.tasks`
   - code-only change → repo `speckit.implement`
3. **Restart through, not just at, that step**: re-run every downstream Stage 02 step in order
   (`specify → clarify → plan → checklist → tasks → analyze`, starting from the routed one), so no
   derived artifact is left stale, then re-run the Stage 02 Mandatory Self-Review Gate
   (read-only, no interview) — global rule 10a.
4. Then re-enter the **full** Stage 03 flow (converge loop, then the `speckit-code-review` loop)
   until `status = pass`. Stage 03's no-stop rules apply again for that re-entry.
5. Return to this gate and repeat until approved.
