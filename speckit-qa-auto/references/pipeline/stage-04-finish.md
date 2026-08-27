# Stage 04 — Finish & PR

Stage 04 validates run state, writes the final report, and manages git commits and PR generation.

## Steps

1. **Validation Gate:** Run `python3 speckit-qa-auto/scripts/validate-run-state.py specs/qa/<issue>/run.json`.
2. **Report Generation:** Present final execution summary:
   - Artifact path
   - Scenario stats (total, NEW, SKIP, REVIEW)
   - Automation results (passed, failed, blocked)
3. **Commit & Push:** Commit artifact files and derived test code using `references/shared/commit.md`. Push branch to remote.
   - *On-Demand Module*: Load `references/modules/ci-matrix-sharding.md` if generating or updating GitHub Actions CI matrix sharding workflows (`.github/workflows/qa-e2e.yml`).
4. **PR (Optional):** If `--pr` was passed, open or update Pull Request. Mark `stage: finished`, `resume_target: done`.
