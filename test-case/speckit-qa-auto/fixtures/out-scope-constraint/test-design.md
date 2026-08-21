# Test Design — MOM-12194: [Invoice Integration] Receive Invoice info from APM

Artifact feature file: `candidate-monitoring-apm-invoice.feature`

## 1. Requirement Analysis → Scenarios

Eight testable behaviours derived from `ticket.md`'s Scenarios table (customfield_10095), one
scenario per behaviour, no behaviour folded into another:

| # | Behaviour | Scenario name | Surface |
|---|---|---|---|
| 1 | Invoice info shown only on Interfaced tab | Invoice information is displayed only on the Interfaced tab | ui |
| 2 | Invoice No rendered as hyperlink | Invoice No is displayed as a hyperlink | ui |
| 3 | Invoice ID hidden, used to build hyperlink href | Invoice ID is not displayed and is used to construct the hyperlink destination | ui |
| 4 | Invoice Status rendered as a tag, 8 supported values | Invoice Status is displayed as a tag with the corresponding supported status (Scenario Outline, 8 rows) | ui |
| 5 | Click-through to APM Invoice Inquiry Detail | Opening Invoice Inquiry Detail from the Invoice No hyperlink | ui |
| 6 | One invoice → multiple candidates, each displays correctly | One invoice attached to multiple candidates displays correctly for each | ui |
| 7 | Kafka consumption + persistence | MOM consumes and persists invoice data published to Kafka | api |
| 8 | Missing/unmatched invoice data handled safely | Missing or unmatched invoice data is not linked to the wrong candidate | api |

## 2. Coverage Matrix

| Acceptance criterion (ticket.md Scenarios table) | Covered by |
|---|---|
| Invoice information visibility | Scenario 1 |
| Invoice No display | Scenario 2 |
| Invoice ID URL construction | Scenario 3 |
| Invoice status tag | Scenario 4 (Outline, 8 examples) |
| Consume and persist invoice data | Scenario 7 |
| Open Invoice Inquiry Detail | Scenario 5 |
| Multiple candidates on one invoice | Scenario 6 |
| Missing or unmatched invoice data | Scenario 8 |

Every acceptance criterion from `ticket.md` maps to at least one scenario. No criterion is
uncovered.

## 3. Dedup Against Xray (2.2)

`xray.query: testRequirement` (confirmed via `linkedIssues` fallback too — same empty result).
`existing-tests.feature`: 0 bytes (genuinely empty — Xray was reachable and the query ran; this is
not a credentials/availability gap). `existing-tests-manual.md`: 0 rows.

`xray.dedup: ran` — mechanically evaluated against an empty Cucumber export, so every behaviour
resolves to `NEW`. This is recorded as `ran` rather than `not-run` because the Xray fetch and the
dedup match both executed successfully; they simply found nothing to match against.

| Scenario | Dedup |
|---|---|
| 1. Invoice information is displayed only on the Interfaced tab | NEW |
| 2. Invoice No is displayed as a hyperlink | NEW |
| 3. Invoice ID is not displayed and is used to construct the hyperlink destination | NEW |
| 4. Invoice Status is displayed as a tag (Outline) | NEW |
| 5. Opening Invoice Inquiry Detail from the Invoice No hyperlink | NEW |
| 6. One invoice attached to multiple candidates displays correctly for each | NEW |
| 7. MOM consumes and persists invoice data published to Kafka | NEW |
| 8. Missing or unmatched invoice data is not linked to the wrong candidate | NEW |

No `UPDATE`, `SKIP`, or `REVIEW` rows — no existing Xray test or repo `.feature` covers this
behaviour (confirmed by Stage 01 discovery: none of the 48 existing repo `.feature` files reference
invoice / candidate-monitoring / interfaced-tab keywords).

## 4. Element Intent Map (2.4) — `surface: ui` scenarios only

`run.code_state: pending` — the frontend (`om-mom-frontend`) currently has only placeholder table
cells (`cell: () => null`) for `invoiceStatus`/`invoiceAmount` columns and no Invoice No column,
hyperlink, or click-through wired up yet. `design.selector_evidence: deferred` — elements are named
in product language below; none are resolved to selectors, because there is nothing built yet to
resolve against.

| Element | Where it appears | What the scenario(s) do with it |
|---|---|---|
| Interfaced tab | Candidate Monitoring page (Work Order Candidate Inquiry), tab bar | Scenarios 1, 2, 3, 4, 5, 6 navigate to it / assert it is the active tab |
| Not Interfaced tab | Candidate Monitoring page, tab bar | Scenario 1 asserts invoice info is absent here |
| Pending Interfaced tab | Candidate Monitoring page, tab bar (sub-state of Not Interfaced per `tabs.ts`) | Scenario 1 asserts invoice info is absent here |
| Invoice No cell (hyperlink) | Candidate row, Interfaced tab table | Scenarios 2, 5 assert its text is the invoice number and that it renders as a hyperlink; Scenario 5 clicks it |
| Invoice No hyperlink `href` | Same cell | Scenario 3 asserts the href is built from base APM URL + Invoice ID (Invoice ID itself is never rendered) |
| Invoice Status tag | Candidate row, Interfaced tab table | Scenario 4 (Outline) asserts the tag text matches each of the 8 supported statuses |
| Candidate row (per candidate) | Interfaced tab table | Scenario 6 asserts each of several candidate rows linked to the same invoice shows correct, independent invoice info |

`Invoice ID` itself carries no visible element — it is explicitly "no need to display" per
`ticket.md`'s Requirements table, so it appears only as an input to the Invoice No hyperlink's
`href`, not as a row of its own.

`surface: api` scenarios (7, 8) name their integration point instead of UI elements, per
`gherkin-conventions.md`:

| Scenario | Endpoint / integration point | Fixture |
|---|---|---|
| 7. Consume and persist | Backend Kafka consumer for APM invoice events, landing in the Work Order Candidate persistence layer (no GraphQL field for invoice data exists yet in `work-order-candidate.generated.ts` — to be added alongside the UI columns) | Seeded Kafka invoice-event fixture: candidate reference + Invoice No/ID/Status payload |
| 8. Missing/unmatched data | Same Kafka consumer, malformed/unmatched-message path | Seeded Kafka invoice-event fixture with a missing or non-matching candidate reference, plus an unrelated control candidate's pre-existing record to assert against |

## 5. Page Objects To Create Or Modify

New domain — none of the existing `src/pages/*` directories cover Candidate Monitoring / Work
Order Candidate. Once code lands:

- `src/pages/candidate-monitoring/CandidateMonitoringPage.ts` (new)
- `src/pages/candidate-monitoring/CandidateMonitoringSelectors.ts` (new)

## 6. Test Data & Mock Plan

- A seeded candidate record attached to an APM invoice, with a full set of Invoice No / Invoice ID
  / Invoice Status fixture values (one fixture per supported status, for the Scenario Outline).
- A seeded multi-candidate-to-one-invoice fixture for Scenario 6.
- A malformed/unmatched invoice-event fixture, plus one unrelated control candidate, for Scenario 8.
- Kafka message fixtures for Scenarios 7 and 8 — shape to be finalized against the real event
  schema once the backend consumer lands (`testdata_path` convention:
  `src/support/candidate-monitoring/fixtures/{name}.json`).

## 7. Open Questions (2.1, non-blocking)

1. How should the UI behave when an edge-case/error invoice state (Cancelled, Not Interfaced,
   Processing/Failed Interfaced — flagged in `ticket.md` as a cross-team error condition) is
   received? Not blocking: none of the 8 designed scenarios depend on the answer, since those
   states are explicitly out of this story's 8 supported-status list.
2. Is there a defined base APM URL configuration source for constructing the Invoice No hyperlink?
   Not blocking for Gherkin — Scenario 3 is written against the business rule ("combine the base
   APM URL with the Invoice ID") independent of where that config value lives.
3. What is the exact Kafka topic/event schema and the GraphQL field names the frontend will read
   once implemented? Not blocking for design — Scenarios 7/8 are written against the business
   behaviour; the endpoint naming above is provisional pending the code landing.

## 8. Self-Review Gate (2.7)

- [x] Every acceptance criterion from `ticket.md` is covered by at least one scenario (§2 above)
- [x] No `TODO`/`TBD`/placeholder in the `.feature` file or this document
- [x] Every `surface: ui` scenario names every element it touches (§4)
- [x] Every `surface: api` scenario names its endpoint/integration point and its fixture (§4)
- [x] No `surface: manual` scenarios in this design
- [x] Every behaviour carries a dedup label (§3) — all `NEW`

All checks pass on first pass.
