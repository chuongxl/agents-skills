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
compatibility:
  github-copilot: "Skill auto-discovered from ~/.agents/skills/. Invoked via skill tool."
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
1. Parse the command:
     --integration <value>   → setup intent
     --issue <url>           → Jira pipeline intent
     --yolo                  → mode = yolo (else mode = default)
     free text               → requirement pipeline intent

2. IF --integration is present:
     → load references/integration-mode.md
     → perform SETUP ONLY: normalize, validate, persist, report
     → END TURN (this is the one legitimate no-pipeline turn end)

3. ELSE (pipeline intent):
     → load references/integration-mode.md
     → resolve provider: repo-local .speckit/integration.json
                       → global ~/.agents/skills/speckit-auto/.state/integration.json
                       → First-Run Selection (ask once, persist, continue same turn)
     → record `integration` in run state (resolved once, never changes mid-run)
     → load references/shared/global-rules.md
     → load references/<provider>/provider-rules.md
     → enter Stage 01 of the resolved provider IMMEDIATELY, in this same turn
```

Never return an acknowledgement-only response. If this skill is already loaded mid-run (a turn
contains `<skill-context name="speckit-auto">`), resume from the current stage using available run
context — never block asking the user to re-run `/speckit-auto`.

## Providers

| `integration` | Provider | Stage directory | Provider rules |
|---------------|----------|-----------------|----------------|
| `github-speckit` | Repo-installed GitHub Spec Kit agents | `references/github-speckit/` | [provider-rules.md](references/github-speckit/provider-rules.md) |
| `superpowers` | `obra/superpowers` skills library | `references/superpowers/` | [provider-rules.md](references/superpowers/provider-rules.md) |

Selection, persistence, resolution precedence, first-run ask, and the full dispatch table:
[references/integration-mode.md](references/integration-mode.md).

## Stage Router (Load On Demand)

Replace `<provider>` with the resolved `integration` value. Never load a stage file from the
provider that was not selected.

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

Shared references, loaded by every provider:

| File | Used at |
|------|---------|
| [references/shared/global-rules.md](references/shared/global-rules.md) | whole run |
| [references/shared/branching.md](references/shared/branching.md) | Stage 01 gate, Stage 03 submodules |
| [references/shared/intake.md](references/shared/intake.md) | Stage 01 |
| [references/shared/preflight-guidelines-context.md](references/shared/preflight-guidelines-context.md) | Stage 01 |

Discard Stage 02 files (and any interview reference) at Stage 03 entry.

## Non-Negotiable Rules

Canonical list: [references/shared/global-rules.md](references/shared/global-rules.md) — load it
once at the start of every pipeline run. The selected provider's `provider-rules.md` adds
provider-specific rules on top; it may never weaken a shared rule.

## Required Inputs

- Requirement text, or a Jira issue link via `--issue <jira link>`
- Jira credentials in root `.env` when using `--issue` (consumed by `jira-to-speckit`):
  `JIRA_URL`, `JIRA_USERNAME`, `JIRA_API_TOKEN`

## Modes

- **Default**: human-in-the-loop checkpoint at Stage 04 (mandatory).
- **YOLO** (`--yolo`): no human checkpoints; Stage 04 skipped, Stage 05 used instead.

Stage 03 is a NO-STOP ZONE in both modes.

## Sub-Skill Dependencies

| Sub-skill | Purpose | Invocation |
|-----------|---------|-----------|
| `jira-to-speckit` | Jira fetch + compaction (steps 1–5 only) | `skill` tool with name `jira-to-speckit` |
| `speckit-code-review` | Authoritative JSON pass/fail review gate | `skill` tool with name `speckit-code-review` |

Both are provider-independent and used by every provider.

## Project Context (Guidelines + Repo Map)

During Stage 01, build a compact in-memory **Project Context** from `docs/guidelines/architecture.md`
if present: repo layout (mono vs single), `repo_map` (which workspace is backend/frontend/BFF/
shared/database), architecture pattern, and links to other guideline `.md` files.

- Built **once**, reused for all stages — never re-read a loaded file.
- Every stage that creates or assigns tasks must consult `repo_map` to target the correct workspace.
- Linked guideline files are discovered from `architecture.md`'s links, loaded **lazily**, cached after first load.
- If `docs/guidelines/` does not exist, skip entirely and continue (no error).

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
