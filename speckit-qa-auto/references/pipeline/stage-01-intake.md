# Stage 01 — Preflight + Intake

Stage 01 initializes the worktree environment, validates provider dependencies, and gathers Jira/Xray or local requirement evidence.

## Steps

1. **Worktree Setup:** Create or link git worktree on branch `qa/<issue-or-slug>` off base branch (`develop → main → master`).
2. **Project Guidelines & Spec Discovery:**
   - Read `docs/guidelines/architecture.md` if available to understand repo structure and testing patterns.
   - Scan existing feature specs under `specs/*/spec.md` to gather contextual domain rules and acceptance criteria.
3. **Requirement Intake:**
   - **Jira Mode (`--issue <key>`):** Read Jira credentials (`JIRA_URL`, `JIRA_USERNAME`, `JIRA_API_TOKEN`) from root `.env`. Invoke `jira-to-speckit` to write `specs/qa/<issue>/ticket.md`.
   - **Local Requirement Mode (Free text prompt):** Write requirement text directly to `specs/qa/<slug>/ticket.md` without requiring Jira credentials.
4. **Xray Export (Optional):** If `--issue` is used and Xray credentials exist, invoke `xray-to-speckit` to write `existing-tests.feature` and `existing-tests-manual.md`. Missing credentials set `coverage.xray: unavailable` and continue.
5. **Initial State:** Initialize `specs/qa/<issue-or-slug>/run.json` with `stage: discovered`, `resume_target: brainstorm`. Validate using `scripts/validate-run-state.py`.
