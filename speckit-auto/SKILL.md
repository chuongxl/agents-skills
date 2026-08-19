---
name: speckit-auto
description: |
  Runs an end-to-end spec-driven delivery pipeline from a requirement or Jira issue using a
  pluggable provider: github-speckit (repo-installed GitHub Spec Kit agents) or superpowers
  (obra/superpowers skills library). Handles provider setup and auto-install, Jira intake via
  jira-to-speckit, spec/design, implementation, a speckit-code-review remediation loop until
  pass, then human review (default) or YOLO commit and push. Use when a feature must go from
  requirement to committed implementation in one run.
compatibility: "Runs on GitHub Copilot, Claude Code, and OpenCode. Discovered from ~/.agents/skills/, ~/.claude/skills/, or ~/.config/opencode/skills/. Requires git and bash; network access for Jira intake via --issue."
license: MIT
allowed-tools: bash glob grep view create edit skill
metadata:
  author: Alex Nguyen
  version: "0.2.8"
---

# Speckit Auto

Small entry point: parse the invocation, resolve the provider, then run the shared pipeline
stages. Load only what the current step needs — stage files say at the top which other files they
load.

## Entry Dispatch (Do This First, Every Invocation)

1. Load [references/shared/host-adaptation.md](references/shared/host-adaptation.md) once per
   run; detect the host (Copilot / Claude Code / OpenCode) from the discovery directory + tool
   surface. The host is fixed for the whole run.

2. Parse the invocation text (slash-command body on Copilot/Claude Code; the natural-language
   trigger message on OpenCode — flags may be embedded anywhere):
   - `--integration <value>` → setup intent (provider setup ONLY, no pipeline)
   - `--issue <url>` → Jira pipeline intent
   - `--yolo` → mode = yolo (else default)
   - free text → requirement pipeline intent

3. **Setup intent** (`--integration` present): load
   [references/shared/integration-setup.md](references/shared/integration-setup.md) and follow
   its steps. END TURN after — do not enter the pipeline.

4. **Pipeline intent** (no `--integration`): resolve the provider from **exactly one source** —
   repo-local `<repo-root>/.speckit/integration.json` → `integration` field. There is no global
   fallback and no first-run prompt:
   - **Missing file, unparseable content, or an unsupported value** → stop immediately and tell
     the user to configure the provider first:
     `/speckit-auto --integration github-speckit` (or `superpowers`).
   - On success, record the result as `integration` in run state; never re-read or change it
     mid-run. Never infer the provider from repo contents — a missing framework installation is
     handled by its provider's install recovery, never by switching provider.

5. Load [references/shared/operating-rules.md](references/shared/operating-rules.md), the
   provider adapter [references/providers/github-speckit.md](references/providers/github-speckit.md)
   or [references/providers/superpowers.md](references/providers/superpowers.md) for the resolved
   provider, then enter Stage 01 **immediately, in this same turn**.

Never return an acknowledgement-only response. If the skill is already loaded mid-run (resume
marker: `<skill-context name="speckit-auto">` on Claude Code, `<available_skills>` on OpenCode,
the skill tool list on Copilot), resume from the current stage using available run context — never
block asking the user to re-run the skill.

## Stage Router (Load On Demand)

Load only the stage file for the current stage; never load a file from the provider that was not
selected.

| Stage | File |
|-------|------|
| 01 — Preflight + Intake | [references/pipeline/stage-01-intake.md](references/pipeline/stage-01-intake.md) |
| 02 — Spec / Design | [references/pipeline/stage-02-spec-design.md](references/pipeline/stage-02-spec-design.md) |
| 03 — Implement + Code Review Loop | [references/pipeline/stage-03-implement-review.md](references/pipeline/stage-03-implement-review.md) |
| 04 — Human Review / Commit / Completion | [references/pipeline/stage-04-finish.md](references/pipeline/stage-04-finish.md) |
| Provider adapter | `references/providers/<provider>.md` |
| Shared operating rules | [references/shared/operating-rules.md](references/shared/operating-rules.md) |
| Host detection / tool names | [references/shared/host-adaptation.md](references/shared/host-adaptation.md) |
| Integration setup (`--integration`) | [references/shared/integration-setup.md](references/shared/integration-setup.md) |
| Commit + push procedure | [references/shared/commit.md](references/shared/commit.md) |

Shared references are loaded by both providers; provider-specific behavior (install layout,
stage agents/skills, artifact paths, fix routing) lives in the provider adapter and is the ONLY
provider-specific file a stage reads. There is no per-provider pipeline tree — both providers run
the same four stage files.

## Modes

- **Default**: human-in-the-loop. Mandatory checkpoints: the Stage 02 approval interactions, the
  Stage 02 → Stage 03 start-implementation confirmation, and Stage 04.
- **YOLO** (`--yolo`): no human checkpoints; all Stage 02 interactions and Stage 04 human review
  are skipped, with an auto-generated commit message.

Stage 03 is a NO-STOP ZONE in both modes (operating rule 8).

## Sub-Skill Dependencies

| Sub-skill | Purpose | Invocation |
|-----------|---------|------------|
| `jira-to-speckit` | Jira fetch + compaction (steps 1–5 only) + ticket snapshot write | `skill` tool, name `jira-to-speckit` |
| `speckit-code-review` | Authoritative JSON pass/fail review gate | `skill` tool, name `speckit-code-review` |

Both are provider-independent and used by every provider.

## Portability Note

`allowed-tools` uses Copilot-style tool names; Claude Code and OpenCode expose the same
capabilities under their own names (`Bash`, `Read`, `Edit`, `Write`, `Glob`, `Grep`, `skill`).
Never refuse to act because a tool is named differently — see host-adaptation.md.

## Required Inputs

- Requirement text, or a Jira issue link via `--issue <jira link>`
- Jira credentials in the project root `.env` (gitignored) when using `--issue`:
  `JIRA_URL`, `JIRA_USERNAME`, `JIRA_API_TOKEN` — consumed by `jira-to-speckit`; never printed.

## Output Behavior

At each checkpoint, report: current stage, result (`done` / `needs changes` / `failed`), next
stage. At completion, report: resolved provider, `speckit-code-review` final status (`pass`),
implementation commit status/hash, and the spec completion commit hash. For a setup invocation
(`--integration`), report: resolved provider, file written, scope, and the next command.