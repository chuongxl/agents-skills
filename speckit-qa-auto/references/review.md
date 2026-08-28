# QA Review

QA review is a required core gate after design and dedup, before automation or finish. It reviews
the QA work product, not automation implementation. The review is read-only.

## Inputs

Package only the evidence needed for review:

- `ticket.md`;
- `run.json`, especially `impact`, `brainstorm`, `conversion`, `coverage`, and `artifacts`;
- `test-design.md`;
- `impact-candidates.md`, when the sweep produced one;
- every source `.feature` path in `artifacts.feature_files`;
- `existing-tests.feature`, `existing-tests-manual.md`, and every `existing-tests-<KEY>*` export;
- repository feature paths used for dedup;
- automation request and likely handoff risks only as context.

Do not rely on session history. Do not read framework-specific automation instructions unless they
are already injected as project skills. Do not mutate source artifacts while reviewing.

## Execution Model

Prefer an isolated reviewer when the host supports subagents or equivalent delegation. Give the
reviewer the packaged inputs above and require read-only behavior. The reviewer must not receive the
main session history as implicit context.

If the host cannot delegate, run the same review inline in the main agent with the same inputs,
checks, severity model, and output expectations. Record the mode in `review.decisions` as
`isolated` or `inline`.

Receiving review findings is always the main agent's responsibility: verify each finding against the
artifact set, accept or reject it with evidence, and update `run.json`.

## Checks

Review for:

- Jira acceptance criteria, risk, and confirmed assumptions all trace to scenarios or explicit
  open gaps — including constraints stated outside the acceptance-criteria table, in Out-Scope,
  Notes, or description prose;
- every entry in `impact.candidates` is either covered by a scenario or recorded in
  `impact.dropped_scenarios` with a reason, and a sweep that could not run says so rather than
  reading as a sweep that found nothing;
- a `source: declared` candidate the sweep could not reach is treated as evidence of a blind spot,
  not as a weaker finding;
- borrowed related-story rules are not asserted as facts unless confirmed;
- dedup labels are plausible and explained where they are `REVIEW`;
- source Gherkin is framework-neutral: no selectors, locators, waits, page/helper names, or runner
  commands;
- scenario count follows YAGNI: no scenario exists without an acceptance criterion, risk,
  regression gap, or explicit human concern;
- important negative, permission, data-state, and edge cases are not missing;
- dedup labels computed by the script were not read as covering manual coverage the script cannot
  parse;
- automation handoff risks are visible as `blocked`, `not-run`, or open issues rather than hidden.

## Conversion Fidelity

When `conversion.converted[]` is non-empty, add the fidelity task set from `manual-conversion.md`
and ask it **both ways**:

- what the source Manual test asserts that the Gherkin does not — a dropped step, a lost
  precondition, an assertion softened into a navigation;
- what the Gherkin asserts that the source does not — an added boundary case, an invented assertion,
  one case silently split into three.

Both directions, because a silent addition is indistinguishable from a mistranslation. A review
asking only what was dropped audits one of the two ways a conversion goes wrong and reports clean on
the other.

An undeclared deviation is a Critical finding regardless of whether the deviation itself was an
improvement. The defect is that it was silent.

## Findings

Classify findings by severity:

| Severity | Meaning |
|---|---|
| `Critical` | Automation/finish would misrepresent coverage, assert an unconfirmed rule, or lose a required scenario. |
| `Important` | The design is materially incomplete, ambiguous, over-specific, or likely to create bad automation. |
| `Minor` | Wording, organization, or reporting polish that does not block the next route. |

Each finding must name the artifact, describe what is wrong, why it matters, and the smallest useful
fix. Vague findings do not block.

## Receiving Findings

Verify findings before changing artifacts. If a finding is unclear, ask for clarification before
partial fixes. Push back when a finding conflicts with the approved brainstorm approach, violates
YAGNI, or is not true for the artifact set.

Handle findings in this order:

1. Critical;
2. Important;
3. simple Minor fixes;
4. remaining Minor notes for finish report.

When Critical or Important findings require source artifact changes, set `review.status:
changes-requested` and route to `resume_target: design`. After fixes, run dedup again and return to
QA review.

## State

Before review passes, keep:

```json
"review": {
  "status": "pending",
  "findings": [],
  "decisions": []
}
```

When review passes, set:

```json
"review": {
  "status": "passed",
  "findings": [],
  "decisions": []
}
```

If findings are accepted or rejected, record them in `decisions` with the reason and evidence. Once
`review.status` is `passed`, set `resume_target: automation` when automation can run or was
requested; otherwise set `resume_target: finish`.
