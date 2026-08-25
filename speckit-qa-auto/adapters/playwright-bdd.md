# Playwright-BDD Adapter

Use this adapter when `scripts/detect-adapter.py` returns `playwright-bdd` or the user explicitly
selects it.

## Contract

Read `run.json`, reviewed source feature files, and `test-design.md`. Do not edit source files
under `docs/qa/<issue>/` to make automation pass.

## Implementation

- Materialize derived feature files into the repository's Playwright-BDD feature location.
- Generate or update step definitions and page objects following local conventions.
- Resolve selectors from source or a live DOM when available; unresolved elements become blocked
  scenarios, not rewritten Gherkin.
- Run the repository's BDD generation command (`bddgen` when present), then the smallest relevant
  Playwright command.
- Use a bounded fix loop for adapter code, selectors, waits, test data, and mocks.

Write `docs/qa/<issue>/automation-result.json` with generated paths and per-scenario status.
