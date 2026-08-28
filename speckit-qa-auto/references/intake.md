# Intake

Intake creates or refreshes the framework-neutral artifact folder. It gathers evidence; it does not
design scenarios and it does not judge coverage.

## Inputs

Require a Jira issue key for a new run. Read Jira credentials from the repository root `.env`:
`JIRA_URL`, `JIRA_USERNAME`, and `JIRA_API_TOKEN`. If any are missing, stop without printing secret
values.

Xray credentials (`XRAY_CLIENT_ID`, `XRAY_CLIENT_SECRET`) are optional. Missing Xray credentials
set `coverage.xray: unavailable` and the run continues.

## Ticket

Invoke `jira-to-speckit` by name with `ticket_output_path: docs/qa/<issue>/ticket.md`.

Name the path explicitly. That skill's default output is a compacted brief returned to the caller;
it writes the full-fidelity snapshot only when the caller supplies the path. The snapshot is what
carries the `updated` and `fetched_at` timestamps that resume freshness compares against, so a run
without it cannot detect a stale ticket.

## Coverage For This Issue

Invoke `xray-to-speckit` by name when Xray credentials are available, with:

- `xray_output_path: docs/qa/<issue>/existing-tests.feature` — Cucumber coverage;
- `xray_manual_output_path: docs/qa/<issue>/existing-tests-manual.md` — Manual and Generic coverage.

Both paths are named for the same reason as the ticket snapshot: that skill writes only the files
the caller names.

An empty Cucumber export is not evidence that the story has no coverage. On a project whose
automation trails its manual suite, the manual file is the larger half of the picture and frequently
the only half.

## Coverage For Related Issues

`xray-to-speckit` discovers tests covering **one** story with one fixed query. A story that is new
has few or no tests linked to it, and the coverage that matters is on sibling stories in the same
flow. Left there, dedup sees an empty corpus and labels every candidate scenario `NEW` — confidently
wrong on a mature project.

`--related` is how a human points at that corpus. For each declared key, invoke `xray-to-speckit`
again with:

- `xray_output_path: docs/qa/<issue>/existing-tests-<KEY>.feature`
- `xray_manual_output_path: docs/qa/<issue>/existing-tests-<KEY>-manual.md`

Record every key exported this way in `coverage.related_issues`. Keep the exports in separate files
rather than concatenating them: dedup reports which file a match came from, and a merged file
reports the wrong provenance for every hit in it.

A key that returns nothing is still recorded. Exported-and-empty and never-exported are different
facts, and only the first is evidence.

## Repository Coverage

Search the repository for `.feature` files outside `docs/qa/<issue>/` and keep their paths as dedup
inputs.

## Hints

Record `--impact` flows as declarations. They are inputs to the impact sweep, not findings of it,
and they stay in their own field — see `impact.md` on why declarations and findings are never
merged.

Record whether the user requested automation and whether the repository appears to have an existing
test stack. Do not select a framework here, and do not encode Playwright, Cypress, Cucumber, or any
other runner in core state. Project/domain/framework skills may be used later if they are already
available in the session.

## State

Create `docs/qa/<issue>/run.json` with:

- `stage: discovered`, `resume_target: impact`;
- `impact.ran: false`, `impact.reason: not-run`, `impact.declared` from `--impact`;
- `brainstorm.status: pending`, `review.status: pending`, `conversion.status: not-run`;
- `automation.status: pending` when automation was requested, `not-requested` otherwise;
- `coverage.related_issues` listing every `--related` key exported;
- pre-design artifacts `{"feature_files": [], "test_design": null}`.

Validate it before leaving intake, then route to `impact`.
