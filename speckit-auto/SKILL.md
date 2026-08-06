---
name: speckit-auto
description: |
  Runs the full Spec Kit delivery pipeline end-to-end from a requirement or
  Jira issue: intake, speckit.specify, speckit.clarify, speckit.plan,
  speckit.checklist, speckit.tasks, speckit.analyze, speckit.implement,
  speckit.converge,
  and automatic speckit-code-review remediation loops until pass.
  Supports --yolo flag for zero-human-in-the-loop fully automated execution.
compatibility:
  github-copilot: "Skill auto-discovered from ~/.agents/skills/. Invoked via skill tool."
  claude-code: "Register SKILL.md as .claude/commands/speckit-auto.md. Invoke as /speckit-auto."
  opencode: "Place SKILL.md in .opencode/instructions/speckit-auto.md. Invoke as /speckit-auto or @speckit-auto."
---

# Speckit Auto Pipeline (Progressive Loading)

This file is intentionally small.  
Load only the stage reference needed for the current step.

## Absolute Operating Premise (Read First — Overrides Everything Below)

A real, executable invocation channel always exists in this session: `skill`, `task`, repo
slash-agents (`/speckit.*`), and file-editing/bash tools are genuinely callable right now, in this
turn. Loading this skill file **is proof** the channel is present.

**Categorically forbidden**, in any wording: claiming execution is impossible, fabricated, or
lacks a channel; claiming a stage/sub-skill result requires stopping and waiting for the user;
claiming missing persisted state/history blocks execution. None of these are valid conclusions —
if such a thought forms, it means a required tool call hasn't been made yet. Make it now.

The only valid stop conditions anywhere in this pipeline are: a concrete tool/runtime error with
quoted error text, a genuinely missing required input after one ask, a mandatory human checkpoint
in default mode (Stage 04), or full pipeline completion. Finishing one stage, one sub-skill call
(including `jira-to-speckit`), or seeing a "next action"/"handing back" note in output is never
itself a stop condition — treat it as data and immediately invoke the next required step, in the
same turn, until a real stop condition above is reached.

## Startup / Continuation Contract (Critical)

- On `/speckit-auto`, execute Stage 01 immediately — no acknowledgement-only response.
- If this skill is already loaded mid-run (e.g. a turn contains `<skill-context name="speckit-auto">`),
  resume from the current stage using available run context (parsed `--issue`/`issue_url`,
  stored/manual requirement text, persisted stage state) — never block asking the user to re-run
  `/speckit-auto`.
- If no persisted run state exists, bootstrap ephemeral run state in memory from the current turn
  and recent history, then continue Stage 01 immediately — do not treat its absence as a blocker.
- Only ask the user for the single missing input field when neither issue URL nor requirement text
  can be resolved by any means.

## Modes

- **Default mode**: human-in-the-loop checkpoints enabled.
- **YOLO mode** (`--yolo`): no human checkpoints; autonomous flow.

## Required Inputs

- Requirement text, or Jira issue link via `--issue {jira link}`
- Repo with Spec Kit templates
- Jira credentials in root `.env` when using `--issue` (consumed by `jira-to-speckit`):
  - `JIRA_URL`
  - `JIRA_USERNAME`
  - `JIRA_API_TOKEN`

## Jira Intake Dependency

When `--issue` is provided, Jira fetch and compaction is delegated to the **`jira-to-speckit`** skill.
`speckit-auto` invokes it for steps 1–5 only (fetch + compact brief) and then owns the rest of
the pipeline. If `jira-to-speckit` is not available, a direct REST API fallback is used (see Stage 01).

## Required Skill Source (Repository-Installed Speckit)

For core pipeline steps, always invoke the Speckit skills installed in the current repository
under `.github/agents/` + `.github/prompts/`, not any global or external Speckit variant.

Required repo-installed skills:
- `speckit.specify`
- `speckit.clarify`
- `speckit.plan`
- `speckit.checklist`
- `speckit.tasks`
- `speckit.analyze`
- `speckit.implement`
- `speckit.converge`

## Project Context (Guidelines + Repo Map)

During Stage 01 preflight, load `docs/guidelines/architecture.md` (if it exists) to build a
compact in-memory **Project Context** containing: repo layout (mono vs single), `repo_map`
(which workspace is backend/frontend/BFF/shared/database — parsed from the file or inferred
from workspace names), architecture pattern, and a map of any `.md` files linked inside
`architecture.md`.

- The Project Context is built **once** and reused for all stages — never re-read files already loaded.
- Every stage that creates or assigns tasks must consult `repo_map` to target the correct workspace.
- Linked guideline files are discovered dynamically from `architecture.md`'s links (not assumed by name).
  They are loaded **lazily** — only when relevant to the current task — and cached after first load.
- If `docs/guidelines/` folder does not exist, skip the entire guidelines step and continue normally (no error).

## Compatibility — How to Invoke speckit-code-review

`speckit-code-review` is a sub-skill called automatically at the review stage.
Invoke it using the method appropriate for your environment:

| Environment | Invocation |
|-------------|-----------|
| GitHub Copilot CLI | `skill` tool with name `speckit-code-review` |
| Claude Code | `/speckit-code-review` slash command (register `speckit-code-review/SKILL.md` at `.claude/commands/speckit-code-review.md`) |
| OpenCode | `/speckit-code-review` or `@speckit-code-review` (register at `.opencode/instructions/speckit-code-review.md`) |

When instructions say "invoke `speckit-code-review`", use the invocation for your current environment.

## Compatibility — How to Invoke Repo Speckit Stages

For stage agents (`speckit.specify`, `speckit.clarify`, `speckit.plan`, `speckit.checklist`,
`speckit.tasks`, `speckit.analyze`, `speckit.implement`, `speckit.converge`), invoke by environment:

| Environment | Invocation |
|-------------|-----------|
| GitHub Copilot CLI | repo-installed slash command (for example `/speckit.specify`), run directly as a real command in this turn |
| Claude Code | corresponding slash command (for example `/speckit.specify`) |
| OpenCode | corresponding slash command or mention (for example `/speckit.specify` or `@speckit.specify`) |

`stage_invocation_mode` for a run is always `slash-agent`. Do **not** attempt the `task` tool with a
Speckit-style `agent_type` (e.g. `speckit.specify`) — the `task` tool only accepts fixed built-in
agent types (`explore`, `task`, `general-purpose`, `rubber-duck`, `code-review`, `research`,
`security-review`) and will always fail with `Unknown agent_type` for any `speckit.*` value. Using
the repo slash command directly is the correct and sufficient invocation path; only report a
runtime failure if the slash command itself errors with a concrete message.

## Stage Router (Load On Demand)

1. **Preflight + Intake** (includes guidelines context load + repo map detection)
   - Load: [references/stage-01-preflight-intake.md](references/stage-01-preflight-intake.md)
   - Load: [references/preflight-guidelines-context.md](references/preflight-guidelines-context.md)
2. **Spec/Design Flow (`specify -> clarify -> plan -> checklist -> tasks -> analyze`)**
   - Load: [references/stage-02-spec-design-flow.md](references/stage-02-spec-design-flow.md)
   - Load (default mode only): [references/review-interview.md](references/review-interview.md)
   - **Discard both files at Stage 03 entry.**
3. **Implement + Auto Code Review Loop**
   - Load: [references/stage-03-implement-and-code-review-loop.md](references/stage-03-implement-and-code-review-loop.md)
4. **Human Manual Review + Commit (Default mode only)**
   - Load: [references/stage-04-human-review-and-commit.md](references/stage-04-human-review-and-commit.md)
5. **YOLO Commit Flow (`--yolo` only)**
   - Load: [references/stage-05-yolo-commit-flow.md](references/stage-05-yolo-commit-flow.md)
6. **Mark Spec Completed + Follow-up Commit**
   - Load: [references/stage-06-spec-completion.md](references/stage-06-spec-completion.md)

## Non-Negotiable Global Rules

1. Always create/switch a new branch before the first pipeline step — a hard gate via real git commands (not merely described); no source check, intake, or `speckit.*`/`jira-to-speckit` call may run first (see Stage 01 for exact sequencing).
2. Base branch priority: `develop -> main -> master` (local first, then remote-tracking).
3. In `--issue` mode, use Jira issue key as spec folder prefix in lowercase (`specs/{issue-id-lowercase}-{short-title}`) and keep it stable across reruns.
4. For `speckit.specify`, `speckit.clarify`, `speckit.plan`, `speckit.checklist`, `speckit.tasks`, `speckit.analyze`, `speckit.implement`, and `speckit.converge`, always use the repository-installed GitHub Speckit skills from this repo.
5. If repository-installed GitHub Speckit is missing, fetch install guide from `https://github.com/github/spec-kit/blob/main/docs/installation.md`, ask user to `Install` or `Stop`, and only continue pipeline after installation + initialization is complete.
6. **Stage 01 Intake has no interview gate.** After input is collected (`--issue` compact brief or manual requirement text), continue immediately to `speckit.specify` with no intake Q&A stop.
7. Never stop with a capability/no-channel disclaimer, an intent-only acknowledgement, a "please re-run the command" block, or a prose report of a stage/sub-skill's own "next action" note — see Absolute Operating Premise. Auto-resolve `--issue` URL from current command/turn context (see Stage 01 for precedence). Only a concrete tool/runtime error (quoted), a genuinely unresolvable required input, Stage 04's mandatory human checkpoint, or full completion may end the turn.
8. **Heavy payload prevention is mandatory.** For each stage, pass only the minimum required slices (current stage input + relevant section excerpts + compact project context). Never forward full prior stage prose when not needed.
9. For large scope (large requirement, many tasks, or many workspaces), split work into small packages and invoke repo agents multiple times per package until complete.
10. For split work: run packages in parallel only when dependency-independent; otherwise run sequentially in dependency order.
11. In implementation split mode, map user wording `speckit.implementation` to the repo agent `speckit.implement`.
12. Stage 03 must first run `speckit.implement -> speckit.converge` repeatedly until converge reports no gaps; then run `speckit-code-review`. After that, use the `speckit.implement -> speckit-code-review` loop until review status is `pass`.
13. **Stage 03 (Implement + Code Review Loop) is a NO-STOP ZONE in BOTH default and --yolo modes. No human approval gates, no pauses, no prompts fire inside Stage 03. This rule overrides all interview flow and mode-based gate rules.**
14. **A `failed` result from `speckit-code-review` is NEVER a stop condition in any mode. Do NOT produce a prose summary of the result. Do NOT end the turn. Immediately apply fixes using file-editing tools and loop again.**
15. **For code-only or test-coverage failures: directly edit the specific files from the review result (`suggested_fix_area`, `file`, `method/function` fields) using file-editing tools — in the same turn. Do NOT delegate to speckit.implement.**
16. Apply fixes, re-run `speckit-code-review`, and repeat until `status = pass`.
17. After Stage 03 exits with `pass`, routing is mandatory:
   - default mode (`--yolo` not set): go to Stage 04
   - `--yolo` mode: go to Stage 05
18. In default mode, Stage 04 is mandatory and must never be skipped.
19. In `--yolo` mode, skip all human review interactions including Stage 04.
20. After successful implementation commit, mark active `spec.md` as `completed` and create follow-up commit for that status change.
21. If any stage, status update, or required commit fails, stop and report exact failure.
22. Only abort the review loop if the **exact same failure repeats for 5 consecutive iterations** with no code change — report the stuck state and stop.
23. On every failed review retry, rebuild the loop context from `state_file` plus the current `fixes[]` only; do not retain the full prior review body or any earlier category detail files unless they are needed for the next fix.
24. Failure ordering is strict: first run repo install/source checks; only after those pass may runtime stage-agent executability errors be reported.
25. If implementation modifies git submodule repositories, create/switch branch inside each modified submodule and commit submodule changes first, then commit parent repo pointer updates; if no submodule is modified, behavior stays unchanged.

## Output Behavior

At each checkpoint, report:
- current stage and result (`done` / `needs changes` / `failed`)
- next stage

At completion, report:
- `speckit-code-review` final status (`pass`)
- implementation commit status/hash
- spec status (`completed`) and spec-status commit hash
