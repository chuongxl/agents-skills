# Stage 03 — Automation & Verification (NO-STOP ZONE)

Stage 03 executes BDD test automation using the resolved provider's tools/skills and verifies test output.

## Operating Rules
- Stage 03 is a **NO-STOP ZONE**: no user prompts or pauses.
- Source `.feature` files in `specs/qa/<issue>/` remain untouched.
- Derived test code is generated in the repository's standard test tree.

## Steps

1. **Provider Automation:** Execute automation via provider skills:
   - `github-speckit`: invoke `speckit-implement` → `speckit-converge`.
   - `superpowers`: invoke `subagent-driven-development` or `executing-plans` under `test-driven-development`.
2. **Inline Verification Pass:**
   - Confirm generated code maps cleanly to source `.feature` scenarios.
   - Run targeted test execution command (`npx bddgen && npx playwright test`) to verify tests pass.
   - If Playwright tests fail, use the `playwright-trace` skill (or inspect `trace.zip` / `playwright-cli`) to diagnose root-cause locator/network/timeout failures before retrying or marking blocked.
   - Confirm source artifacts were not altered to force tests to pass.
3. **Write Results:** Output `automation-result.json`. Update `run.json` (`automation.status: review-passed`, `automation.review.status: passed`, `stage: automation-complete`, `resume_target: finish`).
