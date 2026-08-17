---
name: speckit-auto
description: |
  Runs a full spec-driven delivery pipeline end-to-end from a requirement or Jira issue,
  using a pluggable integration provider: github-speckit (repo-installed GitHub Spec Kit
  agents) or superpowers (obra/superpowers skills library).
  Covers intake, spec/design, implementation, and automatic speckit-code-review
  remediation loops until pass, then commit and completion.
  Use --integration <github-speckit|superpowers> to set the provider (setup only, no pipeline).
  Use --yolo for zero-human-in-the-loop fully automated execution.
compatibility: "Runs on GitHub Copilot, Claude Code, and OpenCode. Discovered from ~/.agents/skills/, ~/.claude/skills/, or ~/.config/opencode/skills/. Requires git and bash; network access for Jira intake via --issue. Providers: github-speckit (Copilot/Claude/OpenCode) or superpowers."
license: MIT
allowed-tools: bash glob grep view create edit skill
metadata:
  author: Alex Nguyen
  version: "0.0.2"
---

# Speckit Auto — Provider Factory

This file is intentionally small. It resolves **which provider runs**, then delegates every stage
to that provider's reference files. Load only what the current step needs.

## Absolute Operating Premise (Read First)

Canonical text: [references/shared/global-rules.md](references/shared/global-rules.md).

Summary: a real, executable invocation channel always exists in this turn — the `skill` tool,
repo slash-agents (for providers that have them), file-editing and bash tools are callable right
now. Loading this file **is proof**. Never claim execution is impossible, fabricated, or
channel-less; never treat a finished stage, a sub-skill result, or a "next action / handing back"
note as a reason to end the turn. If such a thought forms, a required tool call simply hasn't been
made yet — make it now.

## Entry Dispatch (Do This First, Every Invocation)

```
1. Load references/shared/host-adaptation.md once per run. Detect the host agent
   (GitHub Copilot, Claude Code, or OpenCode) from the tool surface and the skill directory this
   file was discovered from. The host is fixed for the whole run.

2. Parse the invocation text (slash-command body on Copilot/Claude Code, or the natural-language
   message that triggered this skill on OpenCode — flags may be embedded anywhere in the text):
     --integration <value>   → setup intent
     --issue <url>           → Jira pipeline intent
     --yolo                  → mode = yolo (else mode = default)
     --no-worktree           → workspace_strategy = branch (else worktree, the default)
     free text               → requirement pipeline intent

3. IF --integration is present:
     → load references/integration-setup.md
     → perform SETUP ONLY: normalize, validate, persist, report
     → END TURN (this is the one legitimate no-pipeline turn end)

4. ELSE (pipeline intent):
     → load references/integration-mode.md
     → resolve provider: repo-local .speckit/integration.json
                       → global <skill-dir>/.state/integration.json
                       → First-Run Selection (ask once, persist, continue same turn)
     → record `integration` in run state (resolved once, never changes mid-run)
     → load references/shared/global-rules.md
     → load references/<provider>/provider-rules.md
     → enter Stage 01 of the resolved provider IMMEDIATELY, in this same turn
```

Never return an acknowledgement-only response. If this skill is already loaded mid-run (the resume
marker varies per host: `<skill-context name="speckit-auto">` on Claude Code, the `<available_skills>`
block on OpenCode, the skill tool list on Copilot), resume from the current stage using available run
context — never block asking the user to re-run the skill.

## Providers + Stage Router (Load On Demand)

Replace `<provider>` with the resolved `integration` value (`github-speckit` or `superpowers`).
Never load a stage file from the provider that was not selected.

| Stage | File |
|-------|------|
| Provider rules (with Stage 01) | `references/<provider>/provider-rules.md` |
| 01 — Preflight + Intake | `references/<provider>/stage-01-preflight-intake.md` |
| 02 — Spec / Design | `references/<provider>/stage-02-spec-design-flow.md` |
| 02 — Review interview (default mode only) | `references/<provider>/review-interview.md` |
| 03 — Implement + Code Review Loop | `references/<provider>/stage-03-implement-and-code-review-loop.md` |
| 04 — Human Review + Commit (default mode only) | `references/<provider>/stage-04-human-review-and-commit.md` |
| 05 — YOLO Commit Flow (`--yolo` only) | `references/<provider>/stage-05-yolo-commit-flow.md` |
| 06 — Mark Completed + Follow-up Commit | `references/<provider>/stage-06-spec-completion.md` |
| Install recovery (only if preflight fails) | `references/<provider>/install-recovery.md` |

- `github-speckit` = repo-installed GitHub Spec Kit agents.
- `superpowers` = the `obra/superpowers` skills library.

Shared references, loaded by every provider:

| File | Used at |
|------|---------|
| [references/shared/global-rules.md](references/shared/global-rules.md) | whole run |
| [references/shared/host-adaptation.md](references/shared/host-adaptation.md) | entry dispatch, every run |
| [references/shared/branching.md](references/shared/branching.md) | Stage 01 gate, Stage 03 submodules |
| [references/shared/intake.md](references/shared/intake.md) | Stage 01 |
| [references/shared/preflight-guidelines-context.md](references/shared/preflight-guidelines-context.md) | Stage 01 |
| [references/shared/scratch-hygiene.md](references/shared/scratch-hygiene.md) | Stage 01 |
| [references/shared/execution-report.md](references/shared/execution-report.md) | Stage 01 (`--issue` only) |
| [references/shared/partitioning.md](references/shared/partitioning.md) | Stage 02/03 when scope is large |
| [references/shared/commit.md](references/shared/commit.md) | Stage 04/05 |

Discard Stage 02 files (and any interview reference) at Stage 03 entry.

## Non-Negotiable Rules

Canonical list: [references/shared/global-rules.md](references/shared/global-rules.md) — load it
once at the start of every pipeline run. The selected provider's `provider-rules.md` adds
provider-specific rules on top; it may never weaken a shared rule.

## Portability Note (Tool Names Vary Per Agent)

This skill's `allowed-tools` uses GitHub Copilot-style tool names (`bash glob grep view create edit skill`).
Claude Code and OpenCode expose the same capabilities under their own names (`Bash`, `Read`, `Edit`,
`Write`, `Glob`, `Grep`, `skill`). See
[references/shared/host-adaptation.md](references/shared/host-adaptation.md) for the per-host tool
map, skill-directory, and invocation-channel differences. Never refuse to act because a tool is named
differently than in `allowed-tools` — the capabilities are equivalent across all three hosts.

## Required Inputs

- Requirement text, or a Jira issue link via `--issue <jira link>`
- Jira credentials in root `.env` when using `--issue` (consumed by `jira-to-speckit`):
  `JIRA_URL`, `JIRA_USERNAME`, `JIRA_API_TOKEN`

## Modes

- **Default**: human-in-the-loop. Pipeline-boundary checkpoints are the Stage 02 → Stage 03
  start-implementation confirmation and Stage 04 (both mandatory). The selected provider also runs
  its own Stage 02 approval interactions (post-stage interviews, or `brainstorming`'s approval) —
  see that provider's `review-interview.md`.
- **YOLO** (`--yolo`): no human checkpoints at all; every Stage 02 interaction, the Stage 03
  confirmation, and Stage 04 are skipped, and Stage 05 is used instead.

Stage 03 is a NO-STOP ZONE in both modes.

## Workspace Strategy

Default is isolation, and repo shape decides how it is realized: a repo with `.gitmodules` keeps the
umbrella branch in-place and worktrees only the submodules the plan names (never a recursive
submodule init); a single repo gets a repo-level worktree. `--no-worktree` opts out to a plain
in-place feature branch everywhere.

Note that in a `.gitmodules` repo the umbrella is branch in-place under **both** strategies, so an
uncommitted umbrella change is a risk on the default path too. Details, including the dirty-tree
confirmation and its `--yolo` resolution:
[references/shared/branching.md](references/shared/branching.md).

## Sub-Skill Dependencies

| Sub-skill | Purpose | Invocation |
|-----------|---------|-----------|
| `jira-to-speckit` | Jira fetch + compaction (steps 1–5 only) + ticket snapshot write | `skill` tool with name `jira-to-speckit` |
| `speckit-code-review` | Authoritative JSON pass/fail review gate | `skill` tool with name `speckit-code-review` |

Both are provider-independent and used by every provider.

## Project Context (Guidelines + Repo Map)

Built once in Stage 01 from `docs/guidelines/architecture.md` (repo layout, `repo_map`, architecture
pattern, links to other guideline files), cached, and reused by every stage that creates or assigns
tasks. Skipped silently when `docs/guidelines/` is absent.
Details: [references/shared/preflight-guidelines-context.md](references/shared/preflight-guidelines-context.md).

## Output Behavior

At each checkpoint, report: current stage, result (`done` / `needs changes` / `failed`), next stage.

At completion, report:
- resolved `integration` provider
- `speckit-code-review` final status (`pass`)
- implementation commit status/hash
- spec/design status (`completed`) and the status commit hash

For a setup invocation (`--integration`), report: resolved provider, file written, scope, and the
next command to run.
