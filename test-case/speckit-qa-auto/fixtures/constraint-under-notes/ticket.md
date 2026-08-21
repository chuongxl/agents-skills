---
jira_key: FIX-0001
jira_url: https://example.invalid/browse/FIX-0001
title: "[Billing] Show settlement reference on the Settled tab"
issue_type: Story
status: IN REFINEMENT
---

# FIX-0001 — [Billing] Show settlement reference on the Settled tab

## Description

**As a** finance operations user,
**I want** the settlement reference shown against each settled charge,
**so that** I can reconcile a charge to its settlement without leaving the page.

**Navigation:** Billing > Charge Inquiry > Settled tab

## Requirements

| Field | Data type | Display | Description |
|---|---|---|---|
| Settlement Ref | String | Hyperlink | The reference of the settlement the charge was included in |
| Settlement ID | String | Not displayed | Combined with the base billing URL to build the hyperlink target |
| Settlement Status | String | Tag | One of: Draft, Pending Approval, Approved, Rejected |

## Notes

- The settlement feed is published nightly; a charge settled after the cut-off appears the
  following day. This is expected and is not a defect.
- Settlement data is read-only in this system. **A charge that has been included in a settlement
  must not be re-rated or re-assigned by any user or by any scheduled job.**
- The finance team has asked for a CSV export of the Settled tab. That is tracked separately.

## Acceptance Criteria

| Scenario | GIVEN | WHEN | THEN |
|---|---|---|---|
| Settlement reference visibility | A charge is included in a settlement and the user opens Charge Inquiry. | The user views the Charge Inquiry tabs. | Settlement information is displayed only on the Settled tab and not on other tabs. |
| Settlement Ref display | The settlement data contains a valid Settlement Ref. | The Settled tab loads the charge. | The Settlement Ref is displayed as a hyperlink. |
| Settlement ID URL construction | The settlement data contains a Settlement ID and the configured base billing URL. | The system renders the settlement link. | Settlement ID is not displayed, and the hyperlink target combines the base billing URL with the Settlement ID. |
| Settlement status tag | The settlement has a supported status: Draft, Pending Approval, Approved, or Rejected. | The Settled tab displays the settlement information. | Settlement Status is displayed as a tag with the corresponding status. |
| Consume and persist settlement data | The nightly settlement feed contains a charge reference and settlement information. | The system consumes the feed. | The settlement is linked to the correct charge and persisted. |
| Open settlement detail | The charge has a valid Settlement Ref and Settlement ID. | The user clicks the Settlement Ref hyperlink. | The corresponding settlement detail page opens. |
| Multiple charges in one settlement | One settlement includes several charges. | The system processes the settlement data. | All and only those charges are linked, and the settlement information displays correctly for each. |
| Missing or unmatched settlement data | Settlement data is missing identifiers or matches no charge. | The system processes the feed record. | No incorrect charge is linked, no unrelated charge data is overwritten, and the record is logged for follow-up. |
