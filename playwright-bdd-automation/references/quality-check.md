# Quality Check

Check Playwright-BDD automation quality after generated or changed test-tree files exist.

## Inputs

Read:

- reviewed source `.feature` files from `docs/qa/<issue>/`, when present;
- `test-design.md`, when present;
- `automation-result.json`;
- the repo profile notes produced before authoring automation;
- changed Playwright-BDD feature copies, `*.steps.ts`, fixtures, mocks, page objects, selectors, and
  helper files;
- command output from BDD generation and Playwright execution.

Prefer an isolated checker when the host supports delegation. If not, check inline with the same
list. The main agent always verifies findings and updates state.

## Checks

Check:

- source scenario business meaning is preserved in materialized feature files and steps;
- implementation follows discovered repo patterns or this skill's defaults when the repo has no
  stronger convention;
- every generated step is bound and exercises real behavior;
- step definitions use the repository's `createBdd(test)`/fixture pattern, await async work, and
  avoid leaking scenario state through module globals;
- assertions prove observable outcomes, not only mocked calls or implementation details;
- page objects/helpers follow repository conventions and do not duplicate existing helpers;
- selectors are stable and semantic where possible;
- waits are condition-based, not arbitrary sleeps;
- fixture data lives in repo-conventional fixtures/builders/loaders rather than hardcoded step
  values or committed secrets;
- mocks are deterministic, scoped, and close to the real API/UI contract;
- BDD generation ran when required;
- command scope proves the changed automation without hiding unrelated failures;
- `automation-result.json` truthfully reports passed, failed, blocked, and not-run scenarios.

## Findings

Use severity:

| Severity | Meaning |
|---|---|
| `Critical` | Automation can falsely pass, changes source QA artifacts, or misrepresents scenario coverage. |
| `Important` | Automation is brittle, incomplete, inconsistent with repo conventions, or lacks meaningful assertions. |
| `Minor` | Naming, organization, or reporting polish that does not block finish. |

Critical and Important findings must be fixed before finish, unless they are recorded as blocked
with a concrete reason. If the finding proves the source QA design is wrong, report that the
orchestrator should resume at QA design instead of patching around it in automation.

After review passes, set `automation.status: review-passed`, `automation.review.status: passed`,
and return control to the orchestrator.
