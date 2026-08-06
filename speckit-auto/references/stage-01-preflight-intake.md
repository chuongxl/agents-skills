# Stage 01: Preflight + Intake

Run this at pipeline start. See `SKILL.md` "Absolute Operating Premise" and "Startup / Continuation
Contract" — they already cover immediate execution, no-acknowledgement-only, resuming mid-run, and
ephemeral state bootstrap; this file adds Stage 01–specific steps only.

## Preflight Branch Setup

**Mandatory gate — must complete before any other Stage 01 action** (source check, guidelines
load, Jira intake, or `speckit.specify`):

1. Create/switch to a new branch before any Speckit stage.
2. Base branch priority: `develop` → `main` → `master` (local first, then remote-tracking).
3. If none exists, stop with missing base-branch error.
4. Branch name must be deterministic:
   - Jira mode: include Jira key
   - Non-Jira mode: requirement slug + timestamp
5. Actually run the git command(s) now (do not describe the plan) and confirm the new branch is
   checked out before proceeding. Set `branch_created: true` and `branch_name` in run state.

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

After source check/recovery passes: invoke `/speckit.specify` directly (the only
`stage_invocation_mode`, `slash-agent` — never attempt `task` with a `speckit.*` agent_type, it
always fails with `Unknown agent_type`). If it runs, executability is proven; only a concrete error
from that call is reportable as a runtime failure (quote it), and only after source check passed.

## Preflight Guidelines Context Load (Required)

After source check passes, load:
- [preflight-guidelines-context.md](preflight-guidelines-context.md)

This step remains optional internally: if `docs/guidelines/` or `architecture.md` is missing,
it must skip and continue (no stop).

## Intake Mode Selection

- If command includes `--issue`, run Jira intake via `jira-to-speckit`.
- Otherwise, start `speckit.specify` from user requirement text.

## Issue Argument Resolution (Critical)

Before deciding intake mode, resolve `issue_url` using this precedence:

1. Explicit CLI flag in current command: `--issue <url>`
2. Explicit CLI flag variant: `--issue=<url>`
3. Any Jira browse URL in the current user turn text (for example `https://.../browse/ABC-123`)
4. Existing in-run state value `issue_url` (if already captured earlier in this same run)
5. Existing in-run state value `original_user_command` (parse `--issue` from it if present)
6. Jira browse URL found in the loaded skill-context payload text (if present in this turn)

If `issue_url` is resolved by any method above, treat the run as `--issue` mode and execute Jira
intake immediately. Do not ask the user to re-invoke the skill with the same command.

Only if the user explicitly selected `--issue` mode but no URL can be resolved, ask once for the
missing Jira URL, then continue Stage 01 in the same run.

If neither issue URL nor manual requirement text can be resolved:
- ask once for the missing requirement input in this run
- continue Stage 01 immediately after receiving it
- do not return "run this command in CLI" as a blocker

## Ephemeral Run-State Bootstrap (When No Persisted Runner State Exists)

If `run_state`/stage file/channel binding is absent in this turn, initialize in memory:

```json
{
  "current_stage": "stage-01",
  "mode": "<default|yolo>",
  "branch_created": false,
  "branch_name": null,
  "issue_url": "<resolved-or-null>",
  "requirement_text": "<resolved-or-null>",
  "stage_invocation_mode": "slash-agent"
}
```

Execute Stage 01 in this order (this is the true order regardless of file position):
**branch setup → source check → runtime check → guidelines load → intake.**
`branch_created` must be `true` (real `branch_name` from an actual git command) before any
Speckit stage, `jira-to-speckit`, or intake step runs.

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

### Continue Immediately After Jira Intake (No Turn-End Here)

A "next action"/"handing back" line in `jira-to-speckit`'s output is data, not a stop cue (see
SKILL.md premise). In the same turn: resolve/create the spec folder (Folder Naming below), then
invoke `/speckit.specify` with the compact brief, and continue Stage 02 onward without waiting for
another user message.

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
