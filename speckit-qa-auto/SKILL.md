---
name: speckit-qa-auto
description: |
  Use when a Jira story, epic, or Xray test key needs framework-neutral QA test design, reviewed deduped BDD scenarios, resumable run state, and optional automation handoff without making Playwright, Cypress, or Cucumber.js part of the core workflow.
compatibility: "Runs on GitHub Copilot, Claude Code, and OpenCode. Discovered from ~/.agents/skills/, ~/.claude/skills/, or ~/.config/opencode/skills/. Requires git, bash, Python 3, Jira credentials, and optional Xray credentials. Automation adapters require their own repository test framework."
license: MIT
allowed-tools: bash glob grep view create edit skill
metadata:
  author: Alex Nguyen
  version: "0.4.0"
---

# Speckit QA Auto

## Entry Point

Resume is step 0. On every invocation, read [references/resume.md](references/resume.md) before
intake or design, even when the user supplies a fresh `--issue`. A run that already has
`docs/qa/<issue>/run.json` continues from `resume_target`; it is not restarted from Jira prose.

After resume routing, read [references/protocol.md](references/protocol.md) once. The protocol is
the core contract for artifact folders, `run.json`, feature files, coverage labels, and adapter
handoff. Keep core outputs framework-neutral.

## Router

Load only the reference needed for the current route:

| Route | Read | Produces |
|---|---|---|
| No existing run | [references/intake.md](references/intake.md) | `ticket.md`, existing coverage exports, initial `run.json` |
| QA brainstorming | [references/brainstorm.md](references/brainstorm.md) | approved test approach and confirmed assumptions |
| Design or revise QA coverage | [references/design.md](references/design.md) | `test-design.md` and source `.feature` files under `docs/qa/<issue>/` |
| Dedup existing coverage | [references/dedup.md](references/dedup.md) | stable `NEW` / `SKIP` / `REVIEW` labels |
| QA review | [references/review.md](references/review.md) | reviewed artifacts and pass/change decisions |
| Automation requested and adapter detected | one file under `adapters/` | `automation-result.json` and materialized test-tree files |
| Final report, commit, or PR | [references/finish.md](references/finish.md) | final run report, validated state, optional branch/PR |

Use `scripts/detect-adapter.py` to select an adapter. If it returns `null`, finish the core QA
artifact workflow without automation. Do not bootstrap a framework from core; adapter setup is a
project decision.

## Core Invariants

- `docs/qa/<issue>/` is the source of truth. Test-tree files are derived adapter output.
- `run.json` is the resume authority. Validate it with `scripts/validate-run-state.py` whenever it
  is created or updated.
- Core references do not know about framework-specific selectors, helper objects, generation
  commands, or step wiring.
- Adapters read reviewed artifacts and write automation results. They may not change the test
  design to make automation pass.
- QA review is required before automation or finish. Critical and Important findings route back to
  design; they are not patched inside an adapter.
- Xray is read-only here. Imports or result uploads belong to the repository's CI, not this skill.
- Missing Xray credentials warn and continue as `coverage.xray: unavailable`; missing Jira
  credentials stop intake.

## Inputs

- `--issue <jira-url-or-key>` — required for a new run; optional for resume when exactly one
  resumable `docs/qa/**/run.json` exists.
- `--related <KEY>[,<KEY>...]` — optional evidence hints for intake/design.
- `--impact "<flow>[, <flow>...]"` — optional impact hints kept separate from discovered coverage.
- `--design-only` — stop after reviewed core artifacts and set `resume_target: automation`.
- `--adapter <id>` — optional override when `scripts/detect-adapter.py` returns multiple plausible
  adapters or the team has a custom adapter.
- `--pr` — request finish to prepare or open a PR after artifacts are validated and committed.

## Sub-Skill Dependencies

Invoke `jira-to-speckit` by name for ticket intake. Invoke `xray-to-speckit` by name for existing
Xray coverage export. Refer to these skills by name only; never link outside this folder.

## Adapter Files

- [adapters/playwright-bdd.md](adapters/playwright-bdd.md)
- [adapters/cypress-cucumber.md](adapters/cypress-cucumber.md)
- [adapters/cucumber-js.md](adapters/cucumber-js.md)

Custom adapters are allowed when they follow [references/protocol.md](references/protocol.md)'s
handoff contract and write `automation-result.json`.
