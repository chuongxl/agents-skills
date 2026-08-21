@REQ_FIX-0001 @Automation
Feature: Settlement reference on the Charge Inquiry Settled tab

  Scenario: Settlement information is displayed only on the Settled tab
    Given a charge is included in a settlement
    When the user opens Charge Inquiry and views each tab
    Then settlement information is displayed on the Settled tab only

  Scenario: Settlement Ref is displayed as a hyperlink
    Given the settlement data contains a valid Settlement Ref
    When the Settled tab loads the charge
    Then the Settlement Ref is displayed as a hyperlink

  Scenario: Settlement ID is not displayed and is used to construct the hyperlink target
    Given the settlement data contains a Settlement ID and the configured base billing URL
    When the system renders the settlement link
    Then the Settlement ID is not displayed
    And the hyperlink target combines the base billing URL with the Settlement ID

  Scenario Outline: Settlement Status is displayed as a tag with the corresponding status
    Given the settlement has status "<status>"
    When the Settled tab displays the settlement information
    Then Settlement Status is displayed as a tag reading "<status>"

    Examples:
      | status           |
      | Draft            |
      | Pending Approval |
      | Approved         |
      | Rejected         |

  Scenario: Opening settlement detail from the Settlement Ref hyperlink
    Given the charge has a valid Settlement Ref and Settlement ID
    When the user clicks the Settlement Ref hyperlink
    Then the corresponding settlement detail page opens

  Scenario: One settlement including multiple charges displays correctly for each
    Given one settlement includes several charges
    When the system processes the settlement data
    Then all and only those charges are linked to that settlement
    And the settlement information displays correctly for each charge

  Scenario: The system consumes and persists settlement data from the nightly feed
    Given the nightly settlement feed contains a charge reference and settlement information
    When the system consumes the feed
    Then the settlement is linked to the correct charge
    And the settlement information is persisted

  Scenario: Missing or unmatched settlement data is not linked to the wrong charge
    Given a feed record is missing identifiers or matches no charge
    When the system processes the record
    Then no incorrect charge is linked
    And no unrelated charge data is overwritten
    And the record is logged for follow-up
