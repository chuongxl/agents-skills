@REQ_MOM-12401
Feature: Vendor certificate validation at invoice time

  Background:
    Given a work order exists with an assigned vendor

  Scenario: Assigning a vendor with an expired certificate is rejected
    Given the vendor certificate expired before today
    When the user assigns the vendor to the work order
    Then the assignment is rejected
    And a validation message names the expired certificate

  Scenario: Invoicing a work order with a valid vendor certificate succeeds
    Given the vendor certificate is valid
    When the user submits the invoice
    Then the invoice is accepted
