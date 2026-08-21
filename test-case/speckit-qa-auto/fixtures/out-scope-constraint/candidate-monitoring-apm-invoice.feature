@REQ_MOM-12194 @Regression_Test @Candidate-Monitoring @MOM-12194
Feature: Receive and display APM invoice information on Candidate Monitoring

  As a local/regional operations user
  I want invoice data automatically synced to MOM whenever an APM invoice linked to a candidate is created
  So that I can track, manage, and update candidate records in MOM in a timely manner

  Scenario: Invoice information is displayed only on the Interfaced tab
    Given a MOM candidate is attached to an APM invoice
    When the user opens Candidate Monitoring and views the candidate tabs
    Then invoice information is displayed on the Interfaced tab
    And invoice information is not displayed on the Not Interfaced tab
    And invoice information is not displayed on the Pending Interfaced tab

  Scenario: Invoice No is displayed as a hyperlink
    Given a MOM candidate is attached to an APM invoice
    And the linked invoice data contains a valid Invoice No
    When the Interfaced tab loads the candidate
    Then the Invoice No is displayed as a hyperlink

  Scenario: Invoice ID is not displayed and is used to construct the hyperlink destination
    Given a MOM candidate is attached to an APM invoice
    And the linked invoice data contains an Invoice ID and the configured base APM URL
    When the system renders the invoice link
    Then the Invoice ID is not displayed
    And the hyperlink destination is constructed by combining the base APM URL with the Invoice ID

  Scenario Outline: Invoice Status is displayed as a tag with the corresponding supported status
    Given a MOM candidate is attached to an APM invoice
    And the invoice has a supported status "<status>"
    When the Interfaced tab displays the invoice information
    Then Invoice Status is displayed as a tag with the status "<status>"

    Examples:
      | status                       |
      | Draft                        |
      | In Discrepancy               |
      | Pending Approval             |
      | 1st Level Approved           |
      | Pending Final Level Approval |
      | Final Level Approved         |
      | Rejected                     |
      | Deleted                      |

  Scenario: Opening Invoice Inquiry Detail from the Invoice No hyperlink
    Given a MOM candidate is attached to an APM invoice
    And the candidate has a valid Invoice No and Invoice ID link
    When the user clicks the Invoice No hyperlink
    Then APM opens the corresponding Invoice Inquiry Detail page

  Scenario: One invoice attached to multiple candidates displays correctly for each
    Given one APM invoice is attached to multiple MOM candidates
    When the user opens Candidate Monitoring and views the Interfaced tab
    Then all and only the corresponding candidates are linked to that invoice
    And the invoice information is displayed correctly for each candidate

  @surface_api
  Scenario: MOM consumes and persists invoice data published to Kafka
    Given APM publishes invoice data to Kafka containing a candidate reference and invoice information
    When MOM consumes the message from the queue
    Then MOM links the invoice to the correct MOM candidate
    And MOM persists the invoice information in the MOM database

  @surface_api
  Scenario: Missing or unmatched invoice data is not linked to the wrong candidate
    Given invoice data is missing required identifiers or does not match a MOM candidate
    When MOM consumes and processes the invoice message
    Then MOM does not link the invoice to an incorrect candidate
    And MOM does not overwrite unrelated candidate data
    And MOM records or safely ignores the unlinked data for follow-up
