---
key: MOM-12550
summary: Automate the invoice list regression pack
status: Ready for QA
updated: 2026-08-25T11:30:00.000+0700
fetched_at: 2026-08-26T14:05:40.000+0700
---

# MOM-12550 — Automate the invoice list regression pack

## Business goal

The invoice list regression pack is executed by hand every release. It is stable and has not changed
in two years. Convert it so it runs in CI.

## Acceptance criteria

| # | Criterion |
|---|---|
| 1 | The behaviour covered by the existing manual pack is covered by automated scenarios |
| 2 | The existing manual tests remain available and unmodified |

## Notes

Nothing about the product changes in this story. Any behavioural difference between a manual test
and its replacement is a defect in the conversion, not an improvement to the suite.
