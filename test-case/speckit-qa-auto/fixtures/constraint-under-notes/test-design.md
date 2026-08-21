# Test Design — FIX-0001: [Billing] Show settlement reference on the Settled tab

Artifact feature file: `charge-inquiry-settlement.feature`

## 1. Requirement Analysis → Scenarios

Eight testable behaviours derived from `ticket.md`'s Acceptance Criteria table, one scenario per
behaviour, no behaviour folded into another.

| # | Behaviour | Scenario name | Surface |
|---|---|---|---|
| 1 | Settlement info shown only on the Settled tab | Settlement information is displayed only on the Settled tab | ui |
| 2 | Settlement Ref rendered as hyperlink | Settlement Ref is displayed as a hyperlink | ui |
| 3 | Settlement ID hidden, used to build the href | Settlement ID is not displayed and is used to construct the hyperlink target | ui |
| 4 | Settlement Status rendered as a tag, 4 values | Settlement Status is displayed as a tag (Outline, 4 rows) | ui |
| 5 | Click-through to settlement detail | Opening settlement detail from the Settlement Ref hyperlink | ui |
| 6 | One settlement → multiple charges | One settlement including multiple charges displays correctly for each | ui |
| 7 | Feed consumption + persistence | The system consumes and persists settlement data from the nightly feed | api |
| 8 | Missing/unmatched data handled safely | Missing or unmatched settlement data is not linked to the wrong charge | api |

## 2. Coverage Matrix

| Acceptance criterion (ticket.md Acceptance Criteria table) | Covered by |
|---|---|
| Settlement reference visibility | Scenario 1 |
| Settlement Ref display | Scenario 2 |
| Settlement ID URL construction | Scenario 3 |
| Settlement status tag | Scenario 4 (Outline, 4 examples) |
| Consume and persist settlement data | Scenario 7 |
| Open settlement detail | Scenario 5 |
| Multiple charges in one settlement | Scenario 6 |
| Missing or unmatched settlement data | Scenario 8 |

Every acceptance criterion from `ticket.md` maps to at least one scenario. **No criterion is
uncovered.**

## 3. Dedup Against Xray

`xray.dedup: ran`, against an empty Cucumber export. Every behaviour resolves to `NEW`.

## 4. Open Questions

1. Where does the base billing URL configuration live? Not blocking — scenario 3 is written against
   the business rule independent of where the value is stored.
