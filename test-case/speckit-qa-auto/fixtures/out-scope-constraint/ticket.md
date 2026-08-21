---
jira_key: MOM-12194
jira_url: https://oneline.atlassian.net/browse/MOM-12194
title: "[Invoice Integration] Receive Invoice info from APM"
issue_type: Story
status: IN REFINEMENT
priority: Medium
labels: [0.0.3]
components: []
assignee: Lien Le
reporter: Lien Le
parent: MOM-9890
fix_versions: [v1.0.0]
created: 2026-07-03T19:31:40.501+0700
updated: 2026-08-20T13:45:18.034+0700
fetched_at: 2026-08-20T07:20:29.000Z
---

# MOM-12194 — [Invoice Integration] Receive Invoice info from APM

## Description

**As a** local/regional operations user,

**I want** invoice data automatically synced to MOM whenever an APM invoice linked to a candidate
is created (regardless of its status),

**so that** I can track, manage, and update candidate records in MOM in a timely manner.

**Navigation:** Work Order (WO) Management > Candidate Monitoring (Inquiry & Amendment)

**In-Scope:**

- Acknowledge that MOM candidates are attached to an invoice.
- Display corresponding invoice information on UI.
- Allow click to Invoice Number hyperlink to navigate to Invoice Inquiry Detail in APM.

**Out-Scope:**

- Handle in-discrepancy invoices.
- Candidate Invoice Amount.
- Payment Due Date.
- Detach candidates from APM's invoice.
- Do not allow user/system modify any candidate has attached to APM's invoice.

### Requirements

**Response Data and Display on UI:** Only allow display the data on Interfaced tab.

| Invoice Information | Data Type | Display on UI | Description | Example |
|---|---|---|---|---|
| Invoice No | String | Hyperlink | The invoice number which corresponds to the invoice where the MOM candidate has been attached on APM | INV12345678 |
| Invoice ID | String | No need to display | MOM will use this value combined with the base APM URL to construct the full URL to open the corresponding invoice on APM. | 1f2657a1-fb65-4aab-8ebf-d67410e7ec1a |
| Invoice Status | String | TAG | Current status of the invoice. In this US, MOM invoice is able to update to the below status: Draft, In Discrepancy, Pending Approval, 1st Level Approved, Pending Final Level Approval, Final Level Approved, Rejected, Deleted | In Discrepancy |

### Logical

1. Whenever APM publishes the invoice data on Kafka, MOM will pull data from the queue → link to
   the correct candidate and store the data in the MOM database.
2. After pulling candidate(s) to APM's invoice → display on Candidate Monitoring page under
   Interfaced tab.
3. Allow clicking on Invoice No to view the invoice's detailed information in APM via a hyperlink.

### Edge Cases

APM-linked candidates in the following states are considered an **error** and need to be checked
on both teams:

1. Cancelled
2. Not Interfaced
3. Processing interfaced
4. Failed Interfaced

## Acceptance Criteria (Scenarios table, verbatim)

| Scenario | GIVEN | WHEN | THEN |
|---|---|---|---|
| Invoice information visibility | A MOM candidate is attached to an APM invoice and the user opens Candidate Monitoring. | The user views the Candidate Monitoring tabs. | Invoice information is displayed only on the Interfaced tab and is not displayed on other tabs. |
| Invoice No display | The linked invoice data contains a valid Invoice No. | The Interfaced tab loads the candidate. | The Invoice No is displayed as a hyperlink. |
| Invoice ID URL construction | The linked invoice data contains an Invoice ID and the configured base APM URL. | The system renders the invoice link. | Invoice ID is not displayed, and the hyperlink destination is constructed by combining the base APM URL with the Invoice ID. |
| Invoice status tag | The invoice has a supported status: Draft, In Discrepancy, Pending Approval, 1st Level Approved, Pending Final Level Approval, Final Level Approved, Rejected, or Deleted. | The Interfaced tab displays the invoice information. | Invoice Status is displayed as a tag with the corresponding supported status. |
| Consume and persist invoice data | APM publishes invoice data to Kafka containing a candidate reference and invoice information. | MOM consumes the message from the queue. | MOM links the invoice to the correct MOM candidate and persists the invoice information in the MOM database. |
| Open Invoice Inquiry Detail | The candidate has a valid Invoice No and Invoice ID link. | The user clicks the Invoice No hyperlink. | APM opens the corresponding Invoice Inquiry Detail page. |
| Multiple candidates on one invoice | One APM invoice is attached to multiple MOM candidates. | MOM consumes and processes the invoice data. | All and only the corresponding candidates are linked to that invoice and the invoice information is displayed correctly for each candidate. |
| Missing or unmatched invoice data | Invoice data is missing required identifiers or does not match a MOM candidate. | MOM consumes and processes the invoice message. | MOM does not link the invoice to an incorrect candidate, does not overwrite unrelated candidate data, and records or safely ignores the unlinked data for follow-up. |

## Attachments

- image-20260818-021331.png (644,429 bytes, uploaded by dat.tran.tpv, 2026-08-18T09:26:54+0700) — Invoice Information mockup
- image-20260818-063555.png (1,274,895 bytes, uploaded by dat.tran.tpv, 2026-08-18T13:36:01+0700) — Invoice Information - Full Table mockup
- Screenshot 2026-08-20 at 09.22.30.png (45,339 bytes, uploaded by dat.tran.tpv, 2026-08-20T09:22:53+0700) — Invoice Status tag screenshot

Figma: https://www.figma.com/design/Bb7uYHMsC2PboEna2VChIL/-MOM--Milestone-3--Marine-Operations-Management?node-id=5844-780588&t=GcwLMWB05MyjS8oH-4
