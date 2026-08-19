---
name: speckit-qa-auto
description: |
  Runs an end-to-end QA delivery pipeline from a Jira issue: requirement analysis, BDD test
  design, selector verification, Playwright-BDD automation, a bounded run-and-fix loop, then
  human review and a pushed branch. The Gherkin feature file is the single artifact, serving
  manual testers and automation alike. Use when a Jira story needs test cases and automated
  tests produced together, from one command.
compatibility: "Runs on GitHub Copilot, Claude Code, and OpenCode. Discovered from ~/.agents/skills/, ~/.claude/skills/, or ~/.config/opencode/skills/. Requires git, bash, and a Playwright-BDD + TypeScript test repository; network access for Jira and Xray."
license: MIT
allowed-tools: bash glob grep view create edit skill
metadata:
  author: Alex Nguyen
  version: "0.1.0"
---

# Speckit QA Auto

## Entry Dispatch (Do This First, Every Invocation)

Load `references/shared/host-adaptation.md` once and fix the host for the rest of the run. Parse
the invocation: `--issue <jira-url-or-key>`, `--yolo`, `--full-suite`, `--pr`.

**`--issue` is required.** A missing `--issue` stops the run, with the reason: the Jira key is the
artifact folder's identity, the `@REQ_` tag every scenario carries, and the dedup key against
existing Xray coverage — three parts of the pipeline have no defined behaviour without it.

Once `--issue` is present, load `references/shared/operating-rules.md` and enter Stage 01 in the
same turn.

## Stage Router

Load only the current stage's file. Each stage names its own successor in prose; the router does
not link ahead, and a stage never links back to the one before it.

| Stage | File | Human gate |
|---|---|---|
| 01 — Intake | `references/pipeline/stage-01-intake.md` | none |
| 02 — Test Design | `references/pipeline/stage-02-test-design.md` | yes (skipped by `--yolo`) |
| 03 — Automate | `references/pipeline/stage-03-automate.md` | none — no-stop zone |
| 04 — Finish | `references/pipeline/stage-04-finish.md` | yes (skipped by `--yolo`) |

Shared leaves, each loaded only by the stage that needs it, never all at once:
`references/shared/run-state.md` (the state contract every stage reads and writes),
`references/shared/operating-rules.md`, `references/shared/workspace-guard.md`,
`references/shared/repo-profile.md`, `references/shared/selector-verification.md`,
`references/shared/gherkin-conventions.md`, `references/shared/host-adaptation.md`,
`references/shared/commit.md`.

## Modes

Default mode gates on human approval at Stage 02 (design) and Stage 04 (commit and push).
`--yolo` skips both approvals but never the Stage 02 selector gate or the Stage 02 self-review
gate — those are hard gates in either mode. Stage 03 is a no-stop zone in both modes: once
entered, it runs to a verdict on every scenario in scope, an infrastructure stop, or the circuit
breaker, and asks no question along the way.

## Sub-Skill Dependencies

| Skill | Invoked | For |
|---|---|---|
| `jira-to-speckit` | By name, through the `skill` tool | Jira ticket intake and Xray existing-test reads (Stage 01) |

Never linked to — a link outside this skill folder fails the validator and breaks the moment this
skill is installed on its own. Refer to it by name only.

## Required Inputs

- `--issue <jira-url-or-key>` — required; see Entry Dispatch.
- `.env` in the repository root: `JIRA_URL`, `JIRA_USERNAME`, `JIRA_API_TOKEN` — required for
  intake. `XRAY_CLIENT_ID`, `XRAY_CLIENT_SECRET` — optional, enable the Xray read in Stage 01.
  None of these are ever printed.

## Portability Note

`allowed-tools` above uses GitHub Copilot's tool names. Claude Code and OpenCode expose the same
capabilities under different names — `Bash`/`bash`, `Read`/`view`, `Write`/`create`, `Edit`/`edit`,
`Glob`/`glob`, `Grep`/`grep`, `Skill`/`skill` — per `references/shared/host-adaptation.md`'s tool
map. Never refuse to act because a tool is named differently than expected.
