# Automation Playbook

Implement Playwright-BDD automation by combining the discovered repo profile with the default
playbook below. Use discovered patterns first. When the repo is sparse or undocumented, these
defaults are enough to proceed without a project-specific automation skill.

## Default File Layout

Prefer the repository's existing names. If no stronger convention exists, use this layout:

| Concern | Default pattern |
|---|---|
| Feature | `src/tests/{domain}/{domain}-{aspect}.feature` |
| Steps | `src/tests/{domain}/{domain}-{aspect}.steps.ts` |
| Page object | `src/pages/{domain}/{DomainAspect}Page.ts` |
| Selectors | `src/pages/{domain}/{DomainAspect}Selectors.ts` |
| Test data | `src/support/{domain}/{domain}-test-data.ts` |
| Fixture JSON | `src/support/{domain}/fixtures/{scenario-or-entity}.json` |
| Mock | `src/support/{domain}/mocks/{domain}.mock.ts` |
| Builder | `src/support/{domain}/builders/{entity}.builder.ts` |

Keep names business-readable and stable. Avoid framework mechanics in feature text.

## Source To Test Tree

Use reviewed QA artifacts as source:

- keep scenario names and business meaning aligned with the source `.feature`;
- preserve Jira/Xray tags where the repository expects them;
- add runner tags such as smoke/regression only when they match existing repo practice;
- place materialized feature files under the repo's existing BDD feature location.

Do not put selectors, waits, page object names, fixture mechanics, or API details into source QA
Gherkin. Those belong in automation code.

## Feature Style

Use one coherent Feature per file unless the repo already groups differently. Use `Background` only
for true shared preconditions. Preserve Jira/Xray tags such as `@MOM-1234`, `@PROJ-1234`, or the
repo's issue-key style. Add test-suite tags (`@smoke`, `@regression`, `@e2e`) only when they already
mean something in that repository.

## Step Definitions

Follow the repository's import and fixture pattern. In a typical Playwright-BDD repo this means:

```typescript
import { createBdd } from 'playwright-bdd';
import { expect } from '@playwright/test';
import { test } from '../fixtures';

const { Given, When, Then } = createBdd(test);
```

Keep steps thin:

- Given sets state or navigation;
- When performs one user or API action;
- Then asserts observable behavior;
- async operations are always awaited;
- shared state is scenario-scoped, not global mutable test state.
- use `{string}`, `{int}`, and `{float}` parameters instead of parsing vague free text when values
  are part of the behavior.

Steps may keep a small scenario state object for data passed between steps. Do not store state in
module globals that can leak between scenarios or workers.

## Page Objects And Selectors

Prefer the repository's existing page object style. If adding a new page object:

- extend the local base page when one exists;
- expose one method per user action or observable read;
- keep assertions in steps unless the repository already uses assertion helpers;
- centralize selectors where the repository centralizes them;
- prefer `data-testid`, role, label, and text selectors before structural CSS.

Avoid `page.waitForTimeout()`. Use existing wait helpers, locator assertions, load-state waits, or
domain-specific readiness checks.

Default selector shape:

```typescript
export const domainAspectSelectors = {
  filters: {
    searchInput: '[data-testid="search-input"]'
  },
  table: {
    rows: '[data-testid="result-row"]'
  },
  buttons: {
    submit: '[data-testid="submit-button"]'
  }
} as const;
```

Default page-object behavior:

- compose local helpers such as table, pagination, navigation, and loader helpers when they exist;
- wrap repeated UI sequences in methods named after user intent, not selectors;
- use locator assertions or the local base page wait helpers to wait for readiness;
- expose text/count/state reads for steps to assert.

## Data, Fixtures, And Mocks

Follow repository conventions for test data. If the repo stores fixture data in JSON or builders,
keep using that pattern. Do not hardcode credentials, rotating pools, mock payloads, or default
business values in step definitions.

Mocks should model the API contract closely. Over-mocking that makes the scenario pass while hiding
real integration behavior must be recorded as a risk or blocked condition.

Default data rules:

- keep default business data in JSON fixtures or builders under the domain support folder;
- load fixtures through an existing loader when present, otherwise add a small domain-local helper
  consistent with repo style;
- keep secrets in environment variables, not committed fixtures;
- make fixture data deterministic and shallow enough to inspect during review.

Default mocking rules:

- prefer the repo's existing route/API mock base;
- GraphQL mocks should match operation names and response shapes, not only URL strings;
- REST mocks should match method, path, status, and payload shape;
- add error variants when the scenario asserts error handling.

## Result

Write `docs/qa/<issue>/automation-result.json` when working from a `speckit-qa-auto` run. Minimum
shape:

```json
{
  "tool": "playwright-bdd",
  "skill": "playwright-bdd-automation",
  "status": "passed",
  "generated": [],
  "changed": [],
  "commands": [],
  "results": [],
  "blocked": [],
  "risks": [],
  "source_artifacts_preserved": true
}
```

Set `run.json` automation state to `implemented` and `automation.review.status: pending` when code
was created or changed. Then generate/run the scoped command and complete the automation quality
check.
