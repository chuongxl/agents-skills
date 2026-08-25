# QA Artifact Protocol

This is the core contract for `speckit-qa-auto`. It is framework-neutral: it defines what artifacts
exist and how adapters consume them, not how a browser or test runner is driven.

## Artifact Folder

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

`existing-tests.feature`, `existing-tests-manual.md`, `brainstorm-notes.md`, `review-notes.md`,
and `automation-result.json` may be absent when the source data, approval notes, review notes, or
automation adapter is unavailable. `run.json`, `ticket.md`, `test-design.md`, and at least one
authored `.feature` file are required before finish.

## run.json

Minimum shape:

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

Allowed `stage` values are `intake`, `discovered`, `brainstorming`, `brainstorm-approved`,
`design-drafting`, `design-approved`, `reviewing`, `review-passed`, `automation`,
`automation-complete`, `finished`, and `blocked`.

Allowed `resume_target` values are `intake`, `brainstorm`, `design`, `review`, `automation`,
`finish`, `done`, or `null`.

Allowed coverage values:

| Field | Values |
|---|---|
| `coverage.dedup` | `not-run`, `ran`, `skipped` |
| `coverage.xray` | `available`, `unavailable`, `not-configured` |

Run `scripts/validate-run-state.py docs/qa/<issue>/run.json` after creating or changing state.

Before design artifacts exist, keep the same keys with empty values:

```json
"artifacts": {
  "feature_files": [],
  "test_design": null
}
```

This pre-design shape is valid for intake, discovery, brainstorming, and design drafting. Feature
files and `test_design` become mandatory when `stage` reaches `design-approved` or `resume_target`
moves to `review`, `automation`, `finish`, or `done`.

Before design starts, `brainstorm.status` may be `pending`. Once `resume_target` is `design`,
`review`, `automation`, `finish`, or `done`, `brainstorm.status` must be `approved`.

Before QA review passes, `review.status` may be `pending` or `changes-requested`. Once
`resume_target` is `automation`, `finish`, or `done`, `review.status` must be `passed`. A
`changes-requested` review routes back to `design` or stays at `review` while the finding is being
clarified.

## Gherkin Contract

Feature files under `docs/qa/<issue>/` are source artifacts for manual and automated QA. They should:

- carry requirement tags such as `@REQ_MOM-1234`;
- keep scenario titles stable enough for dedup;
- include clear starting context in `Background:` or the first `Given`;
- express business behavior, not test-runner mechanics;
- avoid implementation selectors, helper object names, wait strategy, or framework commands.

Adapters may copy or split these files into a test tree, but the reviewed source feature files stay
in `docs/qa/<issue>/`.

## Adapter Handoff

An adapter consumes reviewed artifacts:

- `run.json`;
- all paths in `artifacts.feature_files`;
- `test-design.md`;
- the repository's existing test conventions.

An adapter produces `automation-result.json` with this minimum shape:

```json
{
  "adapter": "playwright-bdd",
  "status": "passed",
  "generated": ["tests/bdd/candidate-invoice.feature"],
  "results": [
    {"scenario": "Attach invoice to candidate", "status": "passed"}
  ],
  "blocked": []
}
```

Statuses are `passed`, `failed`, `blocked`, or `not-run`. A blocked scenario remains in the source
feature file and is reported; it is not deleted from the QA artifact set.
