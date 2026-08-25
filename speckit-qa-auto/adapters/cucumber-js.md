# Cucumber.js Adapter

Use this adapter when `scripts/detect-adapter.py` returns `cucumber-js` or the user explicitly
selects it.

## Contract

The adapter consumes reviewed feature files and emits Cucumber.js glue code. It does not own
scenario design.

## Implementation

- Copy or reference feature files according to the repository's Cucumber.js layout.
- Generate step definitions and support world/hooks that match existing project conventions.
- Keep API clients, fixtures, and UI drivers in support code.
- Run the smallest relevant Cucumber.js command.
- Record failures as adapter failures unless the reviewed Gherkin itself must change; design
  changes route back to `resume_target: design`.

Write `automation-result.json` before finish.
