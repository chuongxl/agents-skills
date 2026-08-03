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

## Preflight Guidelines Context Load (Required)

After the Speckit source check passes, load the Project Context:

- Load: [preflight-guidelines-context.md](preflight-guidelines-context.md)

Execute all steps in that file (detect repo layout, load architecture.md, build in-memory context).
The guidelines context step is **optional** — if `docs/guidelines/` does not exist the pipeline
continues normally without it. Do not block or stop Stage 02 when guidelines are absent.

## Intake Mode Selection

- If command includes `--issue`, run Jira intake via `jira-to-speckit` skill (see below).
- Otherwise skip Jira intake and start at `speckit.specify` with user requirement text.

## Jira Intake (`--issue`) — Delegate to jira-to-speckit

**Do NOT fetch or parse Jira manually.** Delegate the entire Jira fetch + compaction step to the
`jira-to-speckit` skill, which handles credentials, ADF normalisation, size truncation, and brief
compaction correctly.

### Invocation

Invoke `jira-to-speckit` using the method for the current environment:

| Environment | Invocation |
|-------------|-----------|
| GitHub Copilot CLI | `skill` tool with name `jira-to-speckit` |
| Claude Code | `/jira-to-speckit` slash command |
| OpenCode | `/jira-to-speckit` or `@jira-to-speckit` |

Pass the Jira URL as the input.

### Scope Constraint (Critical)

`jira-to-speckit` is an orchestrator with its own full pipeline. **speckit-auto must override that.**

When invoking `jira-to-speckit`, explicitly instruct it to:
> "Perform only the Jira fetch and compaction steps (steps 1–5 of your workflow).
> Produce the compact brief and Jira key. Do NOT run speckit.specify, speckit.plan,
> speckit.tasks, or any other Speckit stage. speckit-auto will own the rest of the pipeline."

### Extract from jira-to-speckit Output

After `jira-to-speckit` returns its compact output, extract:

| Field | Where to find it | Used for |
|-------|-----------------|---------|
| `Jira issue key` | `Jira issue key:` line | Spec ID (reuse as-is, e.g. `FCM-13708`) |
| `Compact brief` | `Compact brief:` section | Input to `speckit.specify` |
| `Open questions` | `Open questions:` list | Seed for `speckit.clarify` |
| `Truncation note` | `Truncation note:` line | Log for context awareness |

### Spec ID and Feature Folder

Use the Jira key directly as the Spec ID — do **not** adopt `jira-to-speckit`'s `US-`/`Task-` prefix:

- Spec ID = Jira key (e.g. `FCM-13708`)
- Feature folder = `specs/<JIRA-KEY>-<summary-slug>/` (e.g. `specs/FCM-13708-reduce-dar-review-time/`)

This naming is stable across reruns.

### Fallback — jira-to-speckit Not Available

If the `jira-to-speckit` skill cannot be invoked:

1. Log: `[Preflight] jira-to-speckit not available — falling back to direct Jira fetch.`
2. Read `JIRA_URL`, `JIRA_USERNAME`, `JIRA_API_TOKEN` from root `.env`.
3. If any variable is missing, stop and instruct the user to populate `.env`.
4. Fetch issue: `GET {JIRA_URL}/rest/api/2/issue/{issueKey}?fields=summary,description,issuetype,status,priority,labels,assignee,fixVersions`
5. On API error:
   - `401`/`403`: report credentials invalid or insufficient permission.
   - `404`: ask user to confirm the Jira issue key.
   - `5xx`: ask user to retry.
6. Compact manually: extract summary, business goal, acceptance criteria, constraints.
7. Set Spec ID = Jira key; set feature folder = `specs/<JIRA-KEY>-<summary-slug>/`.

## Human/YOLO Intake Behavior

- **Default mode**: after `jira-to-speckit` (or fallback) returns the compact brief, confirm with
  the user: "Does this summary correctly reflect the Jira requirement?" before proceeding.
- **YOLO mode**: skip confirmation; accept compact brief autonomously and log any open questions
  as assumptions in the pipeline log.
