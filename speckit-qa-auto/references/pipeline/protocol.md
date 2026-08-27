# QA Artifact Protocol

This is the core contract for `speckit-qa-auto`. It is framework-neutral: it defines what artifacts
exist and how automation consumes them.

## Artifact Folder

Each run owns one folder under `specs/qa/<issue>/`:

```text
specs/qa/<issue>/
  run.json
  ticket.md
  existing-tests.feature
  existing-tests-manual.md
  test-design.md
  <domain>.feature
  automation-result.json
```

`run.json`, `ticket.md`, `test-design.md`, and at least one authored `.feature` file are required before finish.

Validate state with `scripts/validate-run-state.py specs/qa/<issue>/run.json`.
