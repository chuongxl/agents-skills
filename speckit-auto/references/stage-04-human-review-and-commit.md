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
2. Run:
   - `git add -A`
   - `git commit -m "<commit-message>"`

## If Request Changes

1. Collect detailed human feedback.
2. Route restart:
   - requirement change -> `speckit.specify`
   - solution change -> `speckit.plan`
   - task/detail change -> `speckit.tasks`
   - code-only change -> `speckit.implement`
3. Apply fixes.
4. If code changed, invoke `speckit-code-review` again until `pass`.
5. Return to this gate and repeat until approved.
