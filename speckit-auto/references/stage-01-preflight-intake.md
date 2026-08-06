# Stage 01: Preflight + Intake

Run this at pipeline start.

## Critical Startup Rules

1. On `/speckit-auto`, execute Stage 01 immediately.
2. No intent-only acknowledgement.
3. Complete preflight + intake in the same run, then hand off to `speckit.specify`.
4. If this file is reached from an already-loaded skill context turn, continue execution immediately using resolved run context; do not ask user to re-run `/speckit-auto`.
5. Do not treat missing persisted runner artifacts (state file/channel binding) as a blocker; initialize ephemeral run state and continue.
6. Never write a prose explanation of why execution might not be possible before attempting the real tool call. Make the call first (see SKILL.md "Absolute Operating Premise").

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

Run only after source check/recovery passes.

Execution order is strict:
1. Verify/install repo Speckit files first.
2. Invoke `speckit.specify` directly via the repo-installed slash command (`/speckit.specify`) —
   this is the sole `stage_invocation_mode` (`slash-agent`) for this run. Do not attempt the `task`
   tool with a `speckit.*` agent_type first; it always fails with `Unknown agent_type` and is not a
   valid check of runtime executability.

This "check" is simply: call the real slash command for the current stage now. If it runs, runtime
executability is proven and the pipeline continues. Only if that concrete call errors do you report
a runtime execution failure — quote the exact error, after confirming source check already passed.

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
  "stage_invocation_mode": null
}
```

Then execute Stage 01 normally in this exact order, without waiting for a separate re-invocation turn:

**branch setup (mandatory, first) → source check → runtime invocation check → guidelines load → intake**

Do not skip straight to intake/source-check because this bootstrap section appears late in the file —
`branch_created` must be `true`, with a real `branch_name` from an actual git command, before any
Speckit stage, `jira-to-speckit`, or intake step is invoked. If `branch_created` is still `false` when
you reach the Jira/manual intake step, stop and perform Preflight Branch Setup first.


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

### Continue Immediately After Jira Intake (Critical — No Turn-End Here)

`jira-to-speckit` returning its compact brief (even when its own output text ends with a line like
"Next action: handing back to speckit-auto...") is **not** a stopping point and must never become
the final assistant response for the turn. That line is data from the sub-skill, not an instruction
to end your turn — it is `speckit-auto`'s job, not the user's, to act on it.

In the same turn, immediately after receiving the compact brief:
1. Do not print the brief and stop. Do not restate "handing back to speckit-auto" as your own next
   step and end the response there.
2. Resolve/create the spec folder using the Folder Naming rule above.
3. Invoke `speckit.specify` right now via the slash command (`/speckit.specify`), passing the
   compact brief as input, exactly as described in Stage 02 invocation rules.
4. Continue the pipeline (Stage 02 onward) in this same run — do not wait for another user message.

This is a specific case of SKILL.md's Startup Execution Contract and Absolute Operating Premise:
finishing one stage/sub-skill call is never itself a valid reason to end the turn.

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
