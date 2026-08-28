# QA Artifact Protocol

This is the core contract for `speckit-qa-auto`. It is framework-neutral: it defines what artifacts
exist and how automation consumes them, not how a browser, API client, or test runner is driven.

## Artifact Folder

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

Everything except `run.json`, `ticket.md`, `test-design.md`, and at least one authored `.feature`
file may be absent when its source data is unavailable. Those four are required before finish.
`impact-candidates.md` is written on every run whose impact sweep produced or was given candidates;
a sweep that found nothing or could not run records that in `run.json.impact` instead.

Do not add narrative side files for brainstorming or review. Brainstorm approval lives in
`run.json.brainstorm` plus the approach section of `test-design.md`; review findings and decisions
live in `run.json.review`. `impact-candidates.md` is the exception that proves the rule: it has a
writer (the sweep) and two readers (the design gate and QA review), and its table is the form a
human actually reads candidates in. An artifact with no writer and no reader is not part of this
contract.

## run.json

Minimum shape:

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

Allowed `stage` values are `intake`, `discovered`, `impact-analysis`, `brainstorming`,
`brainstorm-approved`, `design-drafting`, `design-approved`, `reviewing`, `review-passed`,
`automation`, `automation-reviewing`, `automation-complete`, `finished`, and `blocked`.

Allowed `resume_target` values are `intake`, `impact`, `brainstorm`, `design`, `review`,
`automation`, `automation-review`, `finish`, `done`, or `null`.

Allowed coverage values:

| Field | Values |
|---|---|
| `coverage.dedup` | `not-run`, `ran`, `skipped` |
| `coverage.xray` | `available`, `unavailable`, `not-configured` |
| `coverage.related_issues` | list of Jira keys exported through `--related`; may be empty |
| `impact.reason` | `ok`, `no-source-access`, `entity-unresolved`, `not-run` |
| `conversion.status` | `not-run`, `pending`, `approved` |

Run `scripts/validate-run-state.py docs/qa/<issue>/run.json` after creating or changing state.

Allowed automation values:

| Field | Values |
|---|---|
| `automation.status` | `not-requested`, `pending`, `deferred`, `implemented`, `review-passed`, `blocked`, `not-run` |
| `automation.review.status` | `not-run`, `pending`, `passed`, `changes-requested` |

Use `automation.tool` for the repository tool/framework actually used, and `automation.skill` for
an injected project/domain/framework skill when one materially shaped the implementation. Both may
be `null`. Do not write a top-level `adapter` field.

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

Before the impact sweep runs, `impact.reason` may be `not-run`. Once `resume_target` has moved past
`impact`, `impact.reason` must record an outcome — `ok`, or the reason the sweep could not run. A
sweep that could not run does not release any gate; it makes its own blindness visible instead.

Once `review.status` is `passed`, every entry in `impact.candidates` must be satisfied: named in
`impact.approved_scenarios`, named in `impact.dropped_scenarios` with a reason, or covered by
`impact.acknowledged_empty: true` when there were no candidates at all. A candidate that is neither
covered nor consciously dropped is coverage the run claimed and never designed. Drops keep their
reason and are never deleted, so a resumed run honours a rejection instead of regenerating the
scenario a human already turned down.

Before design starts, `brainstorm.status` may be `pending`. Once `resume_target` is `design`,
`review`, `automation`, `finish`, or `done`, `brainstorm.status` must be `approved`.

Before QA review passes, `review.status` may be `pending` or `changes-requested`. Once
`resume_target` is `automation`, `finish`, or `done`, `review.status` must be `passed`. A
`changes-requested` review routes back to `design` or stays at `review` while the finding is being
clarified.

`deferred` is the state for QA work that is finished while the code it tests is not. It is not a
weaker `blocked`: `blocked` means automation was attempted and hit a wall, `deferred` means it was
deliberately not attempted yet and is expected later. The two report differently, because a deferred
run is complete QA work and a blocked run is incomplete automation.

Because it is a completion state rather than an escape hatch, `deferred` requires
`review.status: passed` and `automation.requested: true`, and carries its own record:

```json
"automation": {
  "status": "deferred",
  "requested": true,
  "deferred": {
    "reason": "implementation not merged yet",
    "resume_when": "MOM-1234 code is on the target branch"
  },
  "tool": null,
  "skill": null,
  "result": null,
  "review": {"status": "not-run", "findings": []}
}
```

`resume_when` is written in terms a person can check months later. "when the code is done" is not
checkable; "MOM-1234 code is on the target branch" is. The field exists because the person resuming
is frequently not the person who deferred.

When automation code is created or changed, route to `automation-review` with `automation.status:
implemented` and `automation.review.status: pending`. `automation.review.status` must become
`passed` before claiming automation is complete. If automation is `blocked`, `not-run`, or
`not-requested`, record the reason in `automation-result.json` when useful and finish without
claiming automated coverage.

## Gherkin Contract

Feature files under `docs/qa/<issue>/` are source artifacts for manual and automated QA. They should:

- carry requirement tags such as `@REQ_MOM-1234`;
- keep scenario titles stable enough for dedup;
- include clear starting context in `Background:` or the first `Given`;
- express business behavior, not test-runner mechanics;
- avoid implementation selectors, helper object names, wait strategy, or framework commands.

Adapters may copy or split these files into a test tree, but the reviewed source feature files stay
in `docs/qa/<issue>/`.

## Automation Handoff

Automation consumes reviewed artifacts:

- `run.json`;
- all paths in `artifacts.feature_files`;
- `test-design.md`;
- the repository's existing test conventions;
- any project/domain/framework skills already injected into the session.

Automation produces `automation-result.json` with this minimum shape:

```json
{
  "tool": "repo-specific-test-runner",
  "skill": null,
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
