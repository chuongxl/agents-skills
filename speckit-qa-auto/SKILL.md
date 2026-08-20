---
name: speckit-qa-auto
description: |
  Runs an end-to-end QA delivery pipeline from a Jira issue: discovery of linked issues and
  existing tests, requirement analysis, BDD test design, selector verification, Playwright-BDD
  automation, a bounded run-and-fix loop, then human review and a pushed branch. Anchors on a
  story, an epic, or an existing Xray test; converts existing Manual test cases into Gherkin; and
  bootstraps a test framework when the repository has none. The Gherkin feature file is the single
  artifact, serving manual testers and automation alike. Use when a Jira issue needs test cases and
  automated tests produced together, from one command.
compatibility: "Runs on GitHub Copilot, Claude Code, and OpenCode. Discovered from ~/.agents/skills/, ~/.claude/skills/, or ~/.config/opencode/skills/. Requires git, bash, and a TypeScript repository; a Playwright-BDD test tree is used when present and created by bootstrap when absent. Network access for Jira and Xray."
license: MIT
allowed-tools: bash glob grep view create edit skill
metadata:
  author: Alex Nguyen
  version: "0.2.0"
---

# Speckit QA Auto

## Entry Dispatch (Do This First, Every Invocation)

Load `references/shared/host-adaptation.md` once and fix the host for the rest of the run. Parse
the invocation: `--issue <jira-url-or-key>`, `--design-only`, `--full-suite`, `--pr`.

**`--issue` is required.** A missing `--issue` stops the run, with the reason: the Jira key is the
artifact folder's identity, the `@REQ_` tag every scenario carries, and the dedup key against
existing Xray coverage — three parts of the pipeline have no defined behaviour without it.

`--issue` accepts three kinds of key, recorded as `run.anchor_type`:

| Anchor | `anchor_type` | Produces |
|---|---|---|
| A story | `story` | One `.feature` set for that requirement |
| An epic | `epic` | One `.feature` per child issue, each tagged with the child's key |
| An existing Xray test | `test` | Scenarios converted from that test, tagged with the requirement the test links to |

One argument, three resolutions — never a second entry flag. The artifact folder is named
`<jira-key>-<slug>` and that name is also the `@REQ_` target, the dedup key, and the glob the resume
check matches; a second way in would mean a second identity, and every one of those four things
would need a second definition.

Once `--issue` is present, load `references/shared/operating-rules.md` and enter Stage 01 in the
same turn.

## Stage Router

Load only the current stage's file. Each stage names its own successor in prose; the router does
not link ahead, and a stage never links back to the one before it.

| Stage | File | Human gate |
|---|---|---|
| 01 — Intake | `references/pipeline/stage-01-intake.md` | none |
| 02 — Test Design | `references/pipeline/stage-02-test-design.md` | yes |
| 03 — Automate | `references/pipeline/stage-03-automate.md` | none — no-stop zone |
| 04 — Finish | `references/pipeline/stage-04-finish.md` | yes |

Shared leaves, each loaded only by the stage that needs it, never all at once:
`references/shared/run-state.md` (the state contract every stage reads and writes),
`references/shared/operating-rules.md`, `references/shared/workspace-guard.md`,
`references/shared/repo-profile.md`, `references/shared/discovery.md`,
`references/shared/selector-verification.md`, `references/shared/gherkin-conventions.md`,
`references/shared/host-adaptation.md`, `references/shared/commit.md`.

Two further leaves are loaded **conditionally**, by the one stage that needs them and only on the
runs that need them: `references/shared/bootstrap.md` (Stage 01, when discovery found no test
framework) and `references/shared/manual-conversion.md` (Stage 02, when the run converts existing
Manual Xray tests). A repository that already has a test tree never pays for the file that builds
one.

## Modes

There is one mode. Both human gates — Stage 02 design approval and Stage 04 commit-and-push
approval — always run, and so do the Stage 02 self-review gate and the selector gate at the head of
Stage 03. **No flag skips a gate.** An earlier `--yolo` flag that skipped the two approvals has been
removed: its documented effect was to skip approvals, but its actual effect was to let a run whose
Xray dedup never ran ship every scenario as `NEW`, with no human ever seeing the `not-run` label —
which creates a duplicate Xray test for every scenario a team already had.

Stage 03 remains a no-stop zone: once entered, it runs to a verdict on every scenario in scope, an
infrastructure stop, or the circuit breaker, and asks no question along the way.

`--design-only` ends the run after Stage 02 instead of entering Stage 03, leaving
`run.resume_from` set so a later invocation continues into automation. It stops the pipeline early;
it does not skip anything the pipeline would otherwise do. A run whose `run.code_state` resolves to
`pending` behaves this way whether or not the flag was passed — with no code, Stage 03 has nothing
to run against.

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
