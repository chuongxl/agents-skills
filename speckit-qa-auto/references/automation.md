# Automation

Automation is optional execution after reviewed QA artifacts exist. It is framework-neutral at the
core level: use repository discovery and any project/domain/framework skills already available in
the session, but do not hard-code a test framework into `speckit-qa-auto`.

## Inputs

Read:

- `run.json` with `brainstorm.status: approved` and `review.status: passed`;
- `test-design.md`;
- every reviewed source `.feature` file in `artifacts.feature_files`;
- repository test layout, package/build scripts, existing step definitions, helpers, fixtures, and
  conventions;
- any injected project/domain/framework skills that are already active for this repository.

Do not introduce a new automation framework. If the repository has no suitable test stack or the
needed product/test data is absent, record automation as `blocked` or `not-run` with a reason.

## Implementation Rules

- Follow the repository's existing automation patterns.
- Keep `docs/qa/<issue>/` source artifacts unchanged while making automation pass.
- Materialize derived test files only in the repository's normal test tree.
- Keep selectors, waits, mocks, fixtures, page helpers, API clients, and runner details outside the
  source Gherkin.
- Run the smallest meaningful command that covers the generated or updated automation.
- If automation proves the reviewed Gherkin is wrong, stop and route back to `resume_target:
  design`; do not silently rewrite source scenarios.

## State

Before starting, set:

```json
"automation": {
  "status": "pending",
  "requested": true,
  "tool": null,
  "skill": null,
  "result": null,
  "review": {
    "status": "pending",
    "findings": []
  }
}
```

After automation runs or is skipped, write `docs/qa/<issue>/automation-result.json` when there is a
result to report. Include the tool/framework actually used, generated or changed files, commands
run, per-scenario status, blocked reasons, and whether source artifacts were preserved.

Then set `stage: automation-reviewing` and route to `automation-review` when automation code was
created or changed. If automation was `not-run` or `blocked`, route to `finish`.
