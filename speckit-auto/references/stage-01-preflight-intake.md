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

## Preflight Speckit Skill Source Check (Required)

Before Stage 02 or Stage 03 starts, verify repository-installed Speckit skills exist:

- `.github/agents/speckit.specify.agent.md`
- `.github/agents/speckit.clarify.agent.md`
- `.github/agents/speckit.plan.agent.md`
- `.github/agents/speckit.tasks.agent.md`
- `.github/agents/speckit.analyze.agent.md`
- `.github/agents/speckit.converge.agent.md`
- `.github/agents/speckit.implement.agent.md`

And matching prompt files:

- `.github/prompts/speckit.specify.prompt.md`
- `.github/prompts/speckit.clarify.prompt.md`
- `.github/prompts/speckit.plan.prompt.md`
- `.github/prompts/speckit.tasks.prompt.md`
- `.github/prompts/speckit.analyze.prompt.md`
- `.github/prompts/speckit.converge.prompt.md`
- `.github/prompts/speckit.implement.prompt.md`

If any required file is missing, trigger the Missing Speckit Auto-Recovery Flow below.
Do not continue with global/fallback Speckit skills.

## Missing Speckit Auto-Recovery Flow (Required)

If one or more required repo-installed Speckit files are missing:

1. Fetch install guide from:
   - `https://github.com/github/spec-kit/blob/main/docs/installation.md`
2. Present a decision gate:
   - `Install GitHub Speckit`
   - `Stop`
3. If user selects `Stop`, stop immediately and report that Speckit installation is required.
4. If user selects `Install GitHub Speckit`, follow the fetched installation guide exactly.
5. After installation, initialize Spec Kit for this repo:
   - run `specify init . --integration copilot`
6. Then run:
   - `/speckit.constitution`
7. Re-run the preflight source check in this file.
8. If checks pass, continue the original `speckit-auto` request from the correct stage.
9. If installation or init fails, stop and report exact failing step.

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
