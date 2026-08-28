# Speckit QA Auto

**Version**: 0.4.0 — unreleased. Behaviour changes land here without a version bump; the number
moves on the first release, not before.
**Author**: Alex Nguyen

## Overview

`speckit-qa-auto` is one installable skill with a thin orchestrator, a framework-neutral QA
artifact protocol, required impact analysis, required QA brainstorming, required QA review, and
optional automation through repository conventions or injected project skills. It creates or
resumes `docs/qa/<issue>/`, fetches Jira and Xray evidence, sweeps for the flows the story imposes
a new rule on, gets an approved test approach, designs and reviews deduped BDD scenarios, and
reports the result.

The important boundary is:

- **Core**: Jira/Xray intake, artifact folder creation, `run.json`, resume, impact analysis, QA
  brainstorming, `test-design.md`, `.feature` files, Manual-test conversion, dedup, QA review,
  generic automation execution, automation review, and final report.
- **Project skills**: optional framework or domain-specific automation rules injected by the target
  repository or team.

The core still works when no project automation skill exists. It discovers and follows repository
patterns when automation is requested, and records a blocked/not-run result when automation cannot
be implemented honestly.

## Quick Start

```bash
skill speckit-qa-auto --issue MOM-1234
```

Resume is always first. If `docs/qa/MOM-1234/run.json` already exists, the skill validates state and
continues from `resume_target` instead of starting over from Jira.

On a project whose automation trails its manual suite, point the run at the coverage that actually
exists — sibling stories in the same flow, and the flows this story constrains:

```bash
skill speckit-qa-auto --issue MOM-1234 \
  --related MOM-1100,MOM-1180 \
  --impact "Change Setting"
```

When the test design is ready before the code is, finish the QA work and record automation as
deferred rather than blocked:

```bash
skill speckit-qa-auto --issue MOM-1234 --design-only
```

That run ends `finished`, with `automation.status: deferred` carrying why it was deferred and what
makes it resumable. Resuming it later with `--automation` re-reads the ticket first, because a design
reviewed weeks ago was reviewed against a ticket that has since moved.

To request automation after reviewed QA artifacts:

```bash
skill speckit-qa-auto --issue MOM-1234 --automation
```

If a project automation skill is available in the session, use it as additional context. Otherwise
discover the repository's existing test stack and conventions directly.

## Artifact Contract

Each run owns one folder:

```text
docs/qa/<issue>/
  run.json
  ticket.md
  existing-tests.feature
  existing-tests-manual.md
  existing-tests-<KEY>.feature          # one pair per --related key
  existing-tests-<KEY>-manual.md
  impact-candidates.md
  test-design.md
  <domain>.feature
  automation-result.json
```

`run.json` is the source of truth for resume:

```json
{
  "issue": "MOM-1234",
  "stage": "review-passed",
  "resume_target": "automation",
  "automation": {
    "status": "pending",
    "requested": true,
    "tool": null,
    "skill": null,
    "result": null,
    "review": {
      "status": "pending",
      "findings": []
    }
  },
  "impact": {
    "ran": true,
    "reason": "ok",
    "entities": ["work_order_candidate"],
    "declared": [],
    "candidates": [
      {
        "flow": "RefreshWorkOrderCandidates",
        "evidence": "src/graphql/work-order-candidate.graphql:123",
        "writes": "work_order_candidate",
        "existing_tests": [],
        "source": "sweep"
      }
    ],
    "approved_scenarios": ["Refreshing candidates keeps an invoice-attached candidate"],
    "dropped_scenarios": [],
    "acknowledged_empty": false
  },
  "conversion": {
    "status": "not-run",
    "converted": []
  },
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
    "xray": "available",
    "related_issues": []
  }
}
```

Validate it with:

```bash
python3 "$SKILL_DIR/scripts/validate-run-state.py" docs/qa/MOM-1234/run.json
```

`$SKILL_DIR` is the directory this skill is installed in. Scripts are addressed from there, not
relative to the target repository the run works against.

## Core Flow

1. Resume existing state.
2. If no state exists, fetch Jira through `jira-to-speckit`.
3. Fetch existing Xray coverage through `xray-to-speckit` when credentials are available — once for
   the issue, and once more per `--related` key.
4. Run required impact analysis and write `impact-candidates.md`.
5. Run required QA brainstorming and record the approved approach in `run.json`.
6. Create or update `test-design.md`, converting existing Manual tests when the approach elected to.
7. Generate framework-neutral `.feature` files in `docs/qa/<issue>/`.
8. Dedup against Xray, related-issue exports, and repository features.
9. Run required QA review over source artifacts, impact disposition, and dedup decisions.
10. Run generic automation only when requested and the repository has an existing test stack.
11. Review automation output when automation code was created or changed.
12. Finish with a report, a regression recommendation, validated state, and optional commit/PR —
    recording automation as `deferred` when the design is ready before the implementation is.

## Automation

Automation is generic in this skill. Framework-specific rules belong in repository or team skills
that are injected into the session, not in `speckit-qa-auto`.

Automation reads reviewed artifacts and writes `automation-result.json`. It may generate derived
test-tree files, step definitions, fixtures, selectors, page helpers, API clients, or runner config
according to the repository's existing conventions. It may not change `docs/qa/<issue>/` source
artifacts to make tests pass.

## Helper Scripts

- `scripts/validate-run-state.py` validates the minimum `run.json` contract.
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
requires an existing repository test stack or an injected project automation skill.
