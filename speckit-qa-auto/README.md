# Speckit QA Auto

**Version**: 0.4.0 — unreleased. Behaviour changes land here without a version bump; the number
moves on the first release, not before.
**Author**: Alex Nguyen

## Overview

`speckit-qa-auto` is one installable skill with a thin orchestrator, a framework-neutral QA
artifact protocol, required QA brainstorming, required QA review, and optional automation adapters.
It creates or resumes `docs/qa/<issue>/`, fetches Jira and Xray evidence, gets an approved test
approach, designs and reviews deduped BDD scenarios, and reports the result. Automation is an
adapter concern, not a core requirement.

The important boundary is:

- **Core**: Jira/Xray intake, artifact folder creation, `run.json`, resume, QA brainstorming,
  `test-design.md`, `.feature` files, dedup, QA review, and final report.
- **Adapter**: framework-specific materialization and execution for Playwright-BDD, Cypress
  Cucumber, Cucumber.js, or a custom adapter.

The core still works when no automation adapter exists.

## Quick Start

```bash
skill speckit-qa-auto --issue MOM-1234
```

Resume is always first. If `docs/qa/MOM-1234/run.json` already exists, the skill validates state and
continues from `resume_target` instead of starting over from Jira.

To request a specific adapter:

```bash
skill speckit-qa-auto --issue MOM-1234 --adapter playwright-bdd
```

Without `--adapter`, `scripts/detect-adapter.py` inspects the repository and selects an available
adapter when possible.

## Artifact Contract

Each run owns one folder:

```text
docs/qa/<issue>/
  run.json
  ticket.md
  existing-tests.feature
  existing-tests-manual.md
  brainstorm-notes.md
  test-design.md
  <domain>.feature
  review-notes.md
  automation-result.json
```

`run.json` is the source of truth for resume:

```json
{
  "issue": "MOM-1234",
  "stage": "review-passed",
  "resume_target": "automation",
  "adapter": "playwright-bdd",
  "brainstorm": {
    "status": "approved",
    "approach": "api-first-plus-ui-smoke",
    "questions": [],
    "confirmed_assumptions": [],
    "rejected_approaches": ["ui-heavy"]
  },
  "review": {
    "status": "passed",
    "findings": [],
    "decisions": []
  },
  "artifacts": {
    "feature_files": ["docs/qa/MOM-1234/candidate-invoice.feature"],
    "test_design": "docs/qa/MOM-1234/test-design.md"
  },
  "coverage": {
    "dedup": "ran",
    "xray": "available"
  }
}
```

Validate it with:

```bash
python3 speckit-qa-auto/scripts/validate-run-state.py docs/qa/MOM-1234/run.json
```

## Core Flow

1. Resume existing state.
2. If no state exists, fetch Jira through `jira-to-speckit`.
3. Fetch existing Xray coverage through `xray-to-speckit` when credentials are available.
4. Run required QA brainstorming and record the approved approach in `run.json`.
5. Create or update `test-design.md`.
6. Generate framework-neutral `.feature` files in `docs/qa/<issue>/`.
7. Dedup against Xray and repository features.
8. Run required QA review over source artifacts and dedup decisions.
9. Run an adapter only when automation is requested and available.
10. Finish with a report, validated state, and optional commit/PR.

## Adapters

Included adapter references:

- `adapters/playwright-bdd.md`
- `adapters/cypress-cucumber.md`
- `adapters/cucumber-js.md`

Adapters read reviewed artifacts and write `automation-result.json`. They may generate derived
test-tree files, step definitions, fixtures, selectors, page helpers, or runner config. They may not
change `docs/qa/<issue>/` feature design to make tests pass.

## Helper Scripts

- `scripts/validate-run-state.py` validates the minimum `run.json` contract.
- `scripts/detect-adapter.py` detects Playwright-BDD, Cypress Cucumber, or Cucumber.js from
  `package.json`.
- `scripts/dedup-gherkin.py` labels candidate scenarios as `NEW`, `SKIP`, or `REVIEW` against
  existing Gherkin files.

All scripts use the Python standard library only.

## Installation

Copy `speckit-qa-auto` into the host's skill directory. Also install `jira-to-speckit` and
`xray-to-speckit`; this skill invokes them by name for intake and coverage export.

## Compatibility

| Host | Discovery directory |
|---|---|
| GitHub Copilot | `~/.agents/skills/`, `.github/skills/` |
| Claude Code | `~/.claude/skills/` |
| OpenCode | `~/.config/opencode/skills/` |

Requires `git`, `bash`, Python 3, Jira credentials, and optional Xray credentials. Automation
requires whatever framework the selected adapter uses.
