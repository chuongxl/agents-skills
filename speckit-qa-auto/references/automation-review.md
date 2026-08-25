# Automation Review

Automation review is required when automation code was created or changed. It reviews the generated
or updated test-tree code and command results, not the source QA design.

## Inputs

Read:

- `automation-result.json`;
- generated or changed automation files listed in that result;
- reviewed source `.feature` files for comparison;
- relevant repository test conventions and commands.

Prefer an isolated reviewer when delegation is available. If not, run the same review inline. The
main agent always receives findings, verifies them, updates state, and decides the next route.

## Checks

Review for:

- each automated scenario maps to the reviewed source scenario without changing business meaning;
- generated code follows repository conventions;
- selectors, waits, fixtures, mocks, and test data do not hide product defects;
- command scope is narrow enough to be useful and broad enough to prove the changed automation;
- blocked or not-run scenarios are reported honestly;
- source artifacts under `docs/qa/<issue>/` were not edited to make automation pass.

Critical or Important automation findings must be fixed in automation code or recorded as blocked.
If the finding proves the QA design itself is wrong, route back to `resume_target: design`.

## State

When automation code is created or changed, keep `automation.review.status: pending` until review
passes. After review passes, set `stage: automation-complete`, set `automation.status:
review-passed`, set `automation.review.status: passed`, and route to `resume_target: finish`.
