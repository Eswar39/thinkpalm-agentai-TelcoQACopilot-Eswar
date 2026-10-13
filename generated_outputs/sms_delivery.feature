
Feature: Telecom SMS Delivery Confirmation Flow

  As an API consumer / Gateway Operator
  I want the SMS gateway to validate, queue, dispatch, and track SMS messages
  So that outbound messages are reliably delivered and failed attempts are retried with exponential backoff.

  Background:
    Given the SMS Delivery Gateway service is operational
    And the carrier network mock endpoint is configured

  # -------------------------------------------------------------------------
  # Happy Path Scenarios
  # -------------------------------------------------------------------------
  @smoke @happy_path
  Scenario: Successfully send and deliver a standard single SMS within threshold
    Given a valid SMS payload:
      | sender_id | recipient_msisdn | message_body                     |
      | TELCO_TX  | +14155552671     | Your verification code is 492011 |
    When the client posts the SMS payload to "/api/v1/sms/send"
    Then the response status code should be 202 Accepted
    And the message status should initially be "QUEUED"
    And the message is dispatched to the carrier
    When the carrier emits a "DELIVERED" DLR callback within 30 seconds
    Then the message status transitions to "DELIVERED"
    And no retry attempts are scheduled

  # -------------------------------------------------------------------------
  # Validation & Edge Boundaries
  # -------------------------------------------------------------------------
  @validation @boundary
  Scenario Outline: Validate recipient phone number format against E.164 standard
    Given an SMS payload with sender "TELCO_TX", body "Test Message", and recipient "<recipient>"
    When the client posts the SMS payload to "/api/v1/sms/send"
    Then the response status code should be <expected_code>
    And the error response message should match "<expected_error>"

    Examples:
      | recipient       | expected_code | expected_error                             |
      | +14155550199    | 202           | None                                       |
      | +447911123456   | 202           | None                                       |
      | 07911123456     | 400           | Recipient number must be in E.164 format   |
      | +1555           | 400           | Invalid E.164 phone number length          |
      | +1415555abcd    | 400           | Phone number contains non-numeric digits   |
      |                 | 400           | Recipient field is required                |

  @validation @boundary
  Scenario Outline: Payload character length validation for single SMS boundary
    Given an SMS payload with recipient "+14155550199" and a message of <char_count> characters
    When the client posts the SMS payload to "/api/v1/sms/send"
    Then the response status code should be <expected_code>

    Examples:
      | char_count | expected_code |
      | 159        | 202           |
      | 160        | 202           |
      | 161        | 422           |

  # -------------------------------------------------------------------------
  # Timeout, Retry, and Backoff Paths
  # -------------------------------------------------------------------------
  @retry @dlr_timeout
  Scenario: DLR timeout triggers retry and succeeds on second attempt
    Given a valid SMS payload dispatched to recipient "+14155550199"
    And the initial message status is "QUEUED"
    When the carrier fails to provide a DLR within 30 seconds
    Then attempt 1 is marked as "TIMED_OUT"
    And the gateway schedules retry attempt 2 with a delay of 5 seconds
    When retry attempt 2 is dispatched
    And the carrier returns a "DELIVERED" DLR within 10 seconds
    Then the final message status updates to "DELIVERED"
    And total attempts recorded should be 2

  @retry @failure_terminal
  Scenario: Carrier returns FAILED and exhausts all retries resulting in UNDELIVERABLE state
    Given a valid SMS payload dispatched to recipient "+14155550199"
    When carrier returns "FAILED" DLR on attempt 1
    Then the gateway waits 5 seconds and executes retry attempt 2
    When carrier returns "FAILED" DLR on attempt 2
    Then the gateway waits 10 seconds and executes retry attempt 3
    When carrier returns "FAILED" DLR on attempt 3
    Then the gateway waits 20 seconds and executes retry attempt 4
    When carrier returns "FAILED" DLR on attempt 4
    Then the message status is permanently set to "UNDELIVERABLE"
    And an outbound webhook alert is triggered with payload:
      | event             | status        | total_retries |
      | SMS_UNDELIVERABLE | UNDELIVERABLE | 3             |
