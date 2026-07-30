# Stage 01: Preflight + Intake

Load this only when starting the pipeline.

## Preflight Branch Setup

1. Create/switch to a new branch before any Speckit stage.
2. Base branch priority:
   - `develop`
   - `main`
   - `master`
3. Use first existing branch (local first, then remote-tracking refs).
4. If none exists, stop and report missing base branch.
5. Branch name should be deterministic:
   - Jira mode: include Jira key
   - non-Jira mode: include requirement slug + timestamp

## Intake Mode Selection

- If command includes `--issue`, run Jira intake.
- Otherwise skip Jira intake and start at `speckit.specify` with user requirement text.

## Jira Intake (`--issue`)

1. Parse issue key from URL.
2. Read `JIRA_URL`, `JIRA_USERNAME`, `JIRA_API_TOKEN` from root `.env`.
3. Fetch issue via `{JIRA_URL}/rest/api/3/issue/{issueKey}`.
4. Extract: key, summary, description, acceptance/business value, labels/priority/assignee, dependencies/blockers.
5. Build feature folder:
   - `<ISSUE_KEY>-<summary-slug>`
6. Lock and reuse:
   - Spec ID = Jira key
   - feature folder name = `<ISSUE_KEY>-<summary-slug>`

## Human/YOLO Intake Behavior

- **Default mode**: confirm summary and resolve ambiguities before continuing.
- **YOLO mode**: skip questions, accept parsed summary, and log assumptions.
