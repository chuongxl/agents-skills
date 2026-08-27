# Stage 03 — Automation & Verification (NO-STOP ZONE)

Stage 03 executes BDD test automation using the resolved provider's tools/skills and verifies test output.

## Operating Rules
- Stage 03 is a **NO-STOP ZONE**: no user prompts or pauses.
- Source `.feature` files in `specs/qa/<issue>/` remain untouched.
- Derived test code is generated in the repository's standard test tree.

## Steps

1. **Monorepo & Multi-Project Discovery:**
   - Probe repository root and child subdirectories for `package.json`, `playwright.config.ts`, test config, or build project files.
   - Run test execution commands from the workspace directory containing the active test runner.
2. **Provider Automation:** Execute automation via provider skills:
   - `github-speckit`: invoke `speckit-implement` → `speckit-converge`.
   - `superpowers`: invoke `subagent-driven-development` or `executing-plans` under `test-driven-development`.
   - *On-Demand Module*: Load `references/modules/test-data-factory.md` when generating step definitions requiring dynamic data fixtures.
3. **Inline Verification Pass:**
   - Confirm generated code maps cleanly to source `.feature` scenarios.
   - Automatically detect the repository's test framework and run the targeted test execution command to verify tests pass.
   - If tests fail, load `references/modules/flaky-diagnosis.md` and use `playwright-trace` (or inspect `trace.zip` / `playwright-cli`) to classify failure root causes (Product vs Test vs Env vs Data vs Race) before retrying or marking blocked.
   - Confirm source artifacts were not altered to force tests to pass.
4. **Write Results:** Output `automation-result.json`. Update `run.json` (`automation.status: review-passed`, `automation.review.status: passed`, `stage: automation-complete`, `resume_target: finish`).
