# Intake

Intake creates or refreshes the framework-neutral artifact folder. It gathers evidence; it does not
design scenarios.

## Inputs

Require a Jira issue key for a new run. Read Jira credentials from the repository root `.env`:
`JIRA_URL`, `JIRA_USERNAME`, and `JIRA_API_TOKEN`. If any are missing, stop without printing secret
values.

Xray credentials (`XRAY_CLIENT_ID`, `XRAY_CLIENT_SECRET`) are optional. Missing Xray credentials
set `coverage.xray: unavailable` and the run continues.

## Evidence

Invoke `jira-to-speckit` by name to write `ticket.md`.

Invoke `xray-to-speckit` by name when Xray credentials are available. Write:

- `existing-tests.feature` for Cucumber coverage;
- `existing-tests-manual.md` for Manual or Generic coverage.

Search the repository for existing `.feature` files outside `docs/qa/<issue>/` and keep their paths
as dedup inputs. Record explicit `--related` and `--impact` hints as evidence, not verdicts.

Record whether the user requested automation and whether the repository appears to have an existing
test stack. Do not select a framework here, and do not encode Playwright, Cypress, Cucumber, or any
other runner in core state. Project/domain/framework skills may be used later if they are already
available in the session.

## State

Create `docs/qa/<issue>/run.json` with `stage: discovered`, `resume_target: brainstorm`,
`brainstorm.status: pending`, `review.status: pending`, `automation.status: pending` when
automation was requested or `not-requested` otherwise, and pre-design artifacts set to
`{"feature_files": [], "test_design": null}`. Validate it before leaving intake.
