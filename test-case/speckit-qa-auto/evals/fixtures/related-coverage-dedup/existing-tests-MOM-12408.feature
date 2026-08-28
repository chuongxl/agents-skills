@REQ_MOM-12408
Feature: Work order scheduling window

  Scenario: Scheduling a work order outside the service window is rejected
    Given the service window is closed for the selected date
    When the user schedules the work order
    Then the schedule request is rejected
