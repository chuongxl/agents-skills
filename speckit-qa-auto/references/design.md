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
- final scenario list with priority and surface (`ui`, `api`, `manual`, or `mixed`).

Borrowed rules from related issues are not asserted as fact unless this ticket also states them or a
human confirms them. Otherwise keep them in Open Questions and mark any scenario using them as
unconfirmed.

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
- what automation risks or likely repository handoff concerns exist.

On approval, set `stage: design-approved` and `review.status: pending`. Set `resume_target:
review`. Automation and finish are not valid next routes until QA review passes.
