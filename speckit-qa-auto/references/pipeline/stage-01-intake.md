# Stage 01 — Preflight + Intake

Stage 01 initializes the worktree environment, validates provider dependencies, and gathers Jira/Xray evidence.

## Steps

1. **Worktree Setup:** Create or link git worktree on branch `qa/<issue>` off base branch (`develop → main → master`).
2. **Project Guidelines:** Read `docs/guidelines/architecture.md` if available to understand repo structure and testing patterns.
3. **Jira Intake:** Require `--issue <key>`. Read Jira credentials (`JIRA_URL`, `JIRA_USERNAME`, `JIRA_API_TOKEN`) from root `.env`. Invoke `jira-to-speckit` to create `specs/qa/<issue>/ticket.md`.
4. **Xray Export (Optional):** If Xray credentials exist, invoke `xray-to-speckit` to write `existing-tests.feature` and `existing-tests-manual.md`. Missing credentials set `coverage.xray: unavailable` and continue.
5. **Initial State:** Initialize `specs/qa/<issue>/run.json` with `stage: discovered`, `resume_target: brainstorm`. Validate using `scripts/validate-run-state.py`.
