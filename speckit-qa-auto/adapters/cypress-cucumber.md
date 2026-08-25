# Cypress Cucumber Adapter

Use this adapter when `scripts/detect-adapter.py` returns `cypress-cucumber` or the user explicitly
selects it.

## Contract

Read reviewed QA artifacts and preserve them as source. The adapter may create derived `.feature`
files, Cypress step definitions, fixtures, and support helpers in the repository test tree.

## Implementation

- Follow the repository's configured Cucumber preprocessor and Cypress folder layout.
- Map Gherkin steps to Cypress commands without changing business wording in the source artifacts.
- Keep selectors in Cypress support/page helper files, not in `docs/qa/<issue>/` feature files.
- Run the narrow Cypress spec or tag selection that covers the generated scenarios.
- Mark scenarios blocked when the implementation is absent or the design needs revision.

Write `automation-result.json` with generated paths, command output summary, and per-scenario
status.
