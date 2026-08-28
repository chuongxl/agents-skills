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

## Deferring: The Design Is Ready, The Code Is Not

QA design frequently lands before the implementation does. That is not a failure to automate — it is
the normal order of work on a team writing tests from a story rather than from a merged branch.

When `--design-only` was requested, or when the behaviour under test does not exist yet, do not
attempt automation and do not record it as `blocked`. Record it as `deferred`:

```json
"automation": {
  "status": "deferred",
  "requested": true,
  "deferred": {
    "reason": "implementation not merged yet",
    "resume_when": "MOM-1234 code is on the target branch"
  },
  "tool": null,
  "skill": null,
  "result": null,
  "review": {"status": "not-run", "findings": []}
}
```

Then set `stage: finished` and route to `finish`. Write no `automation-result.json`: there is no
result, and an empty one reads as an attempt that produced nothing.

Write `resume_when` so that somebody who was not in this session can check it. The gap between
deferring and resuming is measured in weeks, and the person who resumes is often not the person who
deferred.

Deferring requires `review.status: passed`. A run whose QA work has not been reviewed is not
deferred, it is unfinished — routing it to `finish` under a `deferred` label would report reviewed
coverage that nobody reviewed.

## Re-entry: Resuming Deferred Automation

A resumed deferred run has one problem an ordinary automation route does not: the reviewed design was
written against a ticket and a codebase that have both moved since.

Before writing any automation on re-entry:

1. **Re-read the ticket.** Compare `ticket.md`'s snapshot timestamp against Jira's current `updated`.
   This read is mandatory here — the freshness check is normally opportunistic, and a run that
   deferred straight to finish never performed one. If Jira changed, refresh `ticket.md`, record the
   delta in `test-design.md`, and route to `review` before automating.
2. **Confirm the deferral condition actually holds.** `resume_when` names something checkable; check
   it. Automating against code that still does not exist reproduces the situation that caused the
   deferral, with a failing suite as the new artifact.
3. Then proceed through the ordinary automation route, setting `automation.status: pending`.

If the implementation contradicts the reviewed Gherkin, the existing rule applies unchanged: stop and
route back to `design`. Do not rewrite reviewed scenarios to match whatever the code happens to do —
that converts a test into a description.

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
created or changed. If automation was `not-run`, `blocked`, or `deferred`, route to `finish`.
