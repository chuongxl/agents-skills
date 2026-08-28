# Design

Design turns evidence into human-readable QA artifacts. It stays framework-neutral even when
automation was requested or project automation skills are available.

Design starts only after QA brainstorming is approved. If `brainstorm.status` is absent or
`pending`, route back to `brainstorm.md` before writing design artifacts.

## Test Design

Write `test-design.md` with:

- requirement summary and open questions;
- coverage matrix from Jira acceptance criteria to scenarios;
- existing coverage considered;
- dedup labels and rationale;
- any related-story or impact assumptions that need human confirmation;
- the approved brainstorm approach and rejected alternatives;
- every impact candidate with its disposition — the scenario that covers it, or the reason it was
  dropped;
- final scenario list with priority and surface (`ui`, `api`, `manual`, or `mixed`).

Borrowed rules from related issues are not asserted as fact unless this ticket also states them or a
human confirms them. Otherwise keep them in Open Questions and mark any scenario using them as
unconfirmed.

## Impact Scenarios

Read `impact-candidates.md` and `run.json.impact`. Each candidate is a flow that already writes the
entity this story constrains, and the question for each is narrow: *does this story's rule change
what that flow must do?*

Design a scenario when the answer is yes. Record a drop with its reason when the answer is no — a
drop is a decision, and an undecided candidate is coverage the run will later claim without having
designed it.

Candidates are evidence. `source: declared` means a human named the flow and the sweep could not
reach it; that is the strongest available signal that the sweep has a blind spot, so treat it as at
least as real as a swept finding, never less.

A sweep that could not run (`impact.reason` other than `ok`) does not excuse skipping this section.
Design against the ticket and say in `test-design.md` that impact evidence was unavailable, so the
reviewer knows the gap is known rather than missed.

## Converted Manual Tests

When intake surfaced Manual or Generic Xray coverage and the approved approach converts some of it,
read `manual-conversion.md` before writing those scenarios. Conversion has a different gate from
ordinary design — fidelity to the existing test rather than design quality — and different failure
modes.

Do not convert manual tests that nobody elected to convert. Surfacing them as dedup evidence is
intake's job; converting one is a decision a person makes.

## Feature Files

Write one or more `.feature` files under `docs/qa/<issue>/`. Use business language only. Do not
include selectors, helper object names, locators, waits, or runner setup.

Feature files are the shared artifact for manual testers, Xray import, and automation. Automation
may materialize derived copies later.

## Gates

Before marking design approved, present the design for human review in reader-facing language:

- what behavior is covered;
- what existing coverage was skipped or reused;
- which scenarios are new;
- unresolved assumptions or risks;
- each impact candidate and whether it became a scenario or was dropped, with the reason;
- for converted manual tests, the original steps beside the Gherkin, with every deviation itemized;
- what automation risks or likely repository handoff concerns exist.

Impact candidates are approved on concrete scenario text, not on flow names — that is why the gate
sits here and not at the sweep. Record the outcome in `impact.approved_scenarios` and
`impact.dropped_scenarios`. When the sweep ran and found nothing, and the human confirms there is no
impact, set `impact.acknowledged_empty: true`; an empty approved list on its own says nothing about
whether anybody looked.

Set `conversion.status: approved` and fill `conversion.converted[]` when conversions were approved.

On approval, set `stage: design-approved` and `review.status: pending`. Set `resume_target:
review`. Automation and finish are not valid next routes until QA review passes.
