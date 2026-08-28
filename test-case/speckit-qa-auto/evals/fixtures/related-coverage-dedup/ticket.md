---
key: MOM-12500
summary: Vendor certificate validation on work order assignment
status: Ready for QA
updated: 2026-08-24T09:12:00.000+0700
fetched_at: 2026-08-26T14:02:11.000+0700
---

# MOM-12500 — Vendor certificate validation on work order assignment

## Business goal

Assigning a vendor to a work order must not be possible when the vendor's compliance certificate
has lapsed. Today the check happens at invoice time, which is too late to matter.

## Acceptance criteria

| # | Criterion |
|---|---|
| 1 | Assigning a vendor whose certificate has expired is rejected with a validation message |
| 2 | Assigning a vendor whose certificate is valid succeeds |
| 3 | A certificate expiring within 30 days assigns successfully and raises a warning |
| 4 | Every rejected assignment writes an entry to the vendor audit trail |

## Notes

Criterion 1 mirrors the rule already enforced at invoice time. Criterion 4 mirrors the audit
behaviour the settlement flow already has.
