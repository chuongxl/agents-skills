# Stage 01: Preflight + Intake

Run this at pipeline start.

## Critical Startup Rules

1. On `/speckit-auto`, execute Stage 01 immediately.
2. No intent-only acknowledgement.
3. Complete preflight + intake in the same run, then hand off to `speckit.specify`.

## Preflight Branch Setup

1. Create/switch to a new branch before any Speckit stage.
2. Base branch priority: `develop` → `main` → `master` (local first, then remote-tracking).
3. If none exists, stop with missing base-branch error.
4. Branch name must be deterministic:
   - Jira mode: include Jira key
   - Non-Jira mode: requirement slug + timestamp

## Preflight Speckit Source Check (Required)

Before Stage 02/03, verify repo-installed files exist:

Agents:
- `.github/agents/speckit.specify.agent.md`
- `.github/agents/speckit.clarify.agent.md`
- `.github/agents/speckit.plan.agent.md`
- `.github/agents/speckit.checklist.agent.md`
- `.github/agents/speckit.tasks.agent.md`
- `.github/agents/speckit.analyze.agent.md`
- `.github/agents/speckit.implement.agent.md`
- `.github/agents/speckit.converge.agent.md`

Prompts:
- `.github/prompts/speckit.specify.prompt.md`
- `.github/prompts/speckit.clarify.prompt.md`
- `.github/prompts/speckit.plan.prompt.md`
- `.github/prompts/speckit.checklist.prompt.md`
- `.github/prompts/speckit.tasks.prompt.md`
- `.github/prompts/speckit.analyze.prompt.md`
- `.github/prompts/speckit.implement.prompt.md`
- `.github/prompts/speckit.converge.prompt.md`

If any missing, run recovery below. Do not use global/fallback Speckit.

## Missing Speckit Auto-Recovery (Required)

When any required repo Speckit file is missing:

1. Fetch install guide: `https://github.com/github/spec-kit/blob/main/docs/installation.md`
2. Ask user: `Install GitHub Speckit` or `Stop`
3. If `Stop`, halt and report install required.
4. If `Install`, follow guide exactly.
5. Initialize: `specify init . --integration copilot`
6. Run `speckit.constitution` as an **agent** (not skill):
   - GitHub Copilot CLI: `/speckit.constitution`
   - Claude Code: `/speckit.constitution`
   - OpenCode: `/speckit.constitution` or `@speckit.constitution`
7. Re-run source check.
8. If pass, continue pipeline.
9. If install/init fails, stop with exact failing step.

## Preflight Runtime Executability Check (Required, After Source Check)

Run only after source check/recovery passes.

Execution order is strict:
1. Verify/install repo Speckit files first.
2. Then validate runtime executability by invoking repo stage commands in normal flow
   (starting with `/speckit.specify`).

If runtime cannot execute stage commands:
- Report runtime execution failure **after source check passed**.
- Do not label as installation-missing.
- Include exact failing command + runtime error text.

## Preflight Guidelines Context Load (Required)

After source check passes, load:
- [preflight-guidelines-context.md](preflight-guidelines-context.md)

This step remains optional internally: if `docs/guidelines/` or `architecture.md` is missing,
it must skip and continue (no stop).

## Intake Mode Selection

- If command includes `--issue`, run Jira intake via `jira-to-speckit`.
- Otherwise, start `speckit.specify` from user requirement text.

## Jira Intake (`--issue`) via `jira-to-speckit`

Do not manually parse Jira when `jira-to-speckit` is available.

### Invocation

| Environment | Invocation |
|-------------|-----------|
| GitHub Copilot CLI | `skill` tool with name `jira-to-speckit` |
| Claude Code | `/jira-to-speckit` |
| OpenCode | `/jira-to-speckit` or `@jira-to-speckit` |

Pass Jira URL input.

### Scope Constraint (Critical)

Override `jira-to-speckit` orchestration scope:

> Perform only Jira fetch + compaction (workflow steps 1–5).  
> Return compact brief + Jira key.  
> Do NOT run speckit stages (`specify/plan/tasks/...`).  
> `speckit-auto` owns all subsequent stages.

### Extract from Output

| Field | Source | Use |
|------|--------|-----|
| Jira issue key | `Jira issue key:` | Folder issue-id prefix (lowercase) |
| Compact brief | `Compact brief:` | Input for `speckit.specify` |
| Open questions | `Open questions:` | Seed for `speckit.clarify` |
| Truncation note | `Truncation note:` | Context log |

### Folder Naming (`--issue`)

- Issue ID prefix = lowercase Jira key (example: `ddm-6157`)
- Folder = `specs/<issue-id-lowercase>-<short-title-slug>/`
- Keep stable across reruns.

### Fallback if `jira-to-speckit` Unavailable

1. Log fallback message.
2. Read root `.env`: `JIRA_URL`, `JIRA_USERNAME`, `JIRA_API_TOKEN`.
3. If any missing, stop and request `.env` completion.
4. Fetch issue:
   - `GET {JIRA_URL}/rest/api/2/issue/{issueKey}?fields=summary,description,issuetype,status,priority,labels,assignee,fixVersions`
5. Handle errors:
   - `401/403`: invalid credentials/permission
   - `404`: confirm issue key
   - `5xx`: retry later
6. Compact: summary, business goal, acceptance criteria, constraints.
7. Set folder using lowercase issue-id rule above.

## Intake Behavior

Stage 01 has no interview gate.

- `--issue`: use compact Jira output as Stage 02 input.
- manual input: use user requirement text as Stage 02 input.
- In both cases continue immediately to `speckit.specify`.

If requirement clarity is insufficient, interview happens during `speckit.specify` in Stage 02.
