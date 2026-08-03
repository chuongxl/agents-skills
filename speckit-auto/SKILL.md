---
name: speckit-auto
description: |
  Runs the full Spec Kit delivery pipeline end-to-end from a requirement or
  Jira issue: intake, speckit.specify, speckit.clarify, speckit.plan,
  speckit.tasks, speckit.analyze, speckit.converge, speckit.implement,
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

## Modes

- **Default mode**: human-in-the-loop checkpoints enabled.
- **YOLO mode** (`--yolo`): no human checkpoints; autonomous flow.

## Required Inputs

- Requirement text, or Jira issue link via `--issue {jira link}`
- Repo with Spec Kit templates
- Jira credentials in root `.env` when using `--issue`:
  - `JIRA_URL`
  - `JIRA_USERNAME`
  - `JIRA_API_TOKEN`

## Required Skill Source (Repository-Installed Speckit)

For core pipeline steps, always invoke the Speckit skills installed in the current repository
under `.github/agents/` + `.github/prompts/`, not any global or external Speckit variant.

Required repo-installed skills:
- `speckit.specify`
- `speckit.clarify`
- `speckit.plan`
- `speckit.tasks`
- `speckit.analyze`
- `speckit.converge`
- `speckit.implement`

## Compatibility — How to Invoke speckit-code-review

`speckit-code-review` is a sub-skill called automatically at the review stage.
Invoke it using the method appropriate for your environment:

| Environment | Invocation |
|-------------|-----------|
| GitHub Copilot CLI | `skill` tool with name `speckit-code-review` |
| Claude Code | `/speckit-code-review` slash command (register `speckit-code-review/SKILL.md` at `.claude/commands/speckit-code-review.md`) |
| OpenCode | `/speckit-code-review` or `@speckit-code-review` (register at `.opencode/instructions/speckit-code-review.md`) |

When instructions say "invoke `speckit-code-review`", use the invocation for your current environment.

## Stage Router (Load On Demand)

1. **Preflight + Intake**
   - Load: [references/stage-01-preflight-intake.md](references/stage-01-preflight-intake.md)
2. **Spec/Design Flow (`specify -> clarify -> plan -> tasks -> analyze -> converge`)**
   - Load: [references/stage-02-spec-design-flow.md](references/stage-02-spec-design-flow.md)
3. **Implement + Auto Code Review Loop**
   - Load: [references/stage-03-implement-and-code-review-loop.md](references/stage-03-implement-and-code-review-loop.md)
4. **Human Manual Review + Commit (Default mode only)**
   - Load: [references/stage-04-human-review-and-commit.md](references/stage-04-human-review-and-commit.md)
5. **YOLO Commit Flow (`--yolo` only)**
   - Load: [references/stage-05-yolo-commit-flow.md](references/stage-05-yolo-commit-flow.md)
6. **Mark Spec Completed + Follow-up Commit**
   - Load: [references/stage-06-spec-completion.md](references/stage-06-spec-completion.md)

## Non-Negotiable Global Rules

1. Always create/switch a new branch before the first pipeline step.
2. Base branch priority: `develop -> main -> master` (local first, then remote-tracking).
3. In `--issue` mode, reuse Jira key as Spec ID and keep it stable across reruns.
4. For `speckit.specify`, `speckit.clarify`, `speckit.plan`, `speckit.tasks`, `speckit.analyze`, `speckit.converge`, and `speckit.implement`, always use the repository-installed GitHub Speckit skills from this repo.
5. If repository-installed GitHub Speckit is missing, fetch install guide from `https://github.com/github/spec-kit/blob/main/docs/installation.md`, ask user to `Install` or `Stop`, and only continue pipeline after installation + initialization is complete.
6. After each `speckit.implement`, invoke `speckit-code-review` using the correct invocation for the current environment (see Compatibility table above) and wait for JSON result.
7. **Stage 03 (Implement + Code Review Loop) is a NO-STOP ZONE in BOTH default and --yolo modes. No human approval gates, no pauses, no prompts fire inside Stage 03. This rule overrides all interview flow and mode-based gate rules.**
8. **A `failed` result from `speckit-code-review` is NEVER a stop condition in any mode. Do NOT produce a prose summary of the result. Do NOT end the turn. Immediately apply fixes using file-editing tools and loop again.**
9. **For code-only or test-coverage failures: directly edit the specific files from the review result (`suggested_fix_area`, `file`, `method/function` fields) using file-editing tools — in the same turn. Do NOT delegate to speckit.implement.**
10. Apply fixes, re-run `speckit-code-review`, and repeat until `status = pass`.
11. After Stage 03 exits with `pass`, routing is mandatory:
   - default mode (`--yolo` not set): go to Stage 04
   - `--yolo` mode: go to Stage 05
12. In default mode, Stage 04 is mandatory and must never be skipped.
13. In `--yolo` mode, skip all human review interactions including Stage 04.
14. After successful implementation commit, mark active `spec.md` as `completed` and create follow-up commit for that status change.
15. If any stage, status update, or required commit fails, stop and report exact failure.
16. Only abort the review loop if the **exact same failure repeats for 5 consecutive iterations** with no code change — report the stuck state and stop.
17. On every failed review retry, rebuild the loop context from `state_file` plus the current `fixes[]` only; do not retain the full prior review body or any earlier category detail files unless they are needed for the next fix.

## Output Behavior

At each checkpoint, report:
- current stage and result (`done` / `needs changes` / `failed`)
- next stage

At completion, report:
- `speckit-code-review` final status (`pass`)
- implementation commit status/hash
- spec status (`completed`) and spec-status commit hash
