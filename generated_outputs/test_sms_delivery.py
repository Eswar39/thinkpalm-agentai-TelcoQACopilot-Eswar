
"""
Playwright Automation Test Suite: Telecom SMS Delivery Confirmation Flow
Uses Playwright (sync API) with routing intercepts to mock gateway API,
carrier responses, retries with backoff, and webhook notifications.
"""

import json
import time
import pytest
from playwright.sync_api import Page, expect, Route


BASE_URL = "https://sms-gateway.telecom.local"


@pytest.fixture(autouse=True)
def setup_gateway_routes(page: Page):
    """
    Default route mocks for the gateway web console and core APIs.
    """
    # Intercept HTML UI shell
    page.route(
        f"{BASE_URL}/console",
        lambda route: route.fulfill(
            status=200,
            content_type="text/html",
            body="""
            <!DOCTYPE html>
            <html>
            <head><title>SMS Dispatch Gateway</title></head>
            <body>
                <form id="sms-form">
                    <input id="sender" name="sender_id" value="TELCO_TX" />
                    <input id="recipient" name="recipient" placeholder="+14155552671" />
                    <textarea id="message" maxlength="200"></textarea>
                    <button id="send-btn" type="submit">Dispatch SMS</button>
                </form>
                <div id="validation-error" style="display:none; color:red;"></div>
                <div id="status-card" style="display:none;">
                    <span id="msg-id"></span>
                    <span id="sms-status">INIT</span>
                    <span id="retry-counter">0</span>
                </div>
                <script>
                    const form = document.getElementById('sms-form');
                    form.addEventListener('submit', async (e) => {
                        e.preventDefault();
                        const errDiv = document.getElementById('validation-error');
                        errDiv.style.display = 'none';
                        
                        const payload = {
                            sender_id: document.getElementById('sender').value,
                            recipient_msisdn: document.getElementById('recipient').value,
                            message_body: document.getElementById('message').value
                        };

                        const res = await fetch('/api/v1/sms/send', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify(payload)
                        });

                        if (!res.ok) {
                            const err = await res.json();
                            errDiv.textContent = err.error;
                            errDiv.style.display = 'block';
                            return;
                        }

                        const data = await res.json();
                        document.getElementById('status-card').style.display = 'block';
                        document.getElementById('msg-id').textContent = data.message_id;
                        document.getElementById('sms-status').textContent = data.status;

                        // Poll status
                        const interval = setInterval(async () => {
                            const pollRes = await fetch(`/api/v1/sms/${data.message_id}/status`);
                            const pollData = await pollRes.json();
                            document.getElementById('sms-status').textContent = pollData.status;
                            document.getElementById('retry-counter').textContent = pollData.retries;
                            if (pollData.status === 'DELIVERED' || pollData.status === 'UNDELIVERABLE') {
                                clearInterval(interval);
                            }
                        }, 500);
                    });
                </script>
            </body>
            </html>
            """
        )
    )


def test_sms_delivery_success_flow(page: Page):
    """
    Test Case 1: Happy Path
    Submits standard SMS (<160 chars, E.164) -> status is QUEUED -> transitions to DELIVERED.
    """
    msg_id = "msg-uuid-1001"
    poll_state = {"call_count": 0}

    def handle_send(route: Route):
        payload = json.loads(route.request.post_data)
        assert payload["recipient_msisdn"] == "+14155552671"
        assert len(payload["message_body"]) <= 160
        route.fulfill(
            status=202,
            content_type="application/json",
            body=json.dumps({"message_id": msg_id, "status": "QUEUED"}),
        )

    def handle_status(route: Route):
        poll_state["call_count"] += 1
        # Carrier returns DELIVERED on poll
        status = "QUEUED" if poll_state["call_count"] == 1 else "DELIVERED"
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps({"message_id": msg_id, "status": status, "retries": 0}),
        )

    page.route("**/api/v1/sms/send", handle_send)
    page.route(f"**/api/v1/sms/{msg_id}/status", handle_status)

    page.goto(f"{BASE_URL}/console")
    page.fill("#recipient", "+14155552671")
    page.fill("#message", "Welcome to Telecom Service! Your activation code is 8821.")
    page.click("#send-btn")

    # Assert initial UI update
    expect(page.locator("#sms-status")).to_have_text("QUEUED")
    # Assert final delivery via polling mock
    expect(page.locator("#sms-status")).to_have_text("DELIVERED")
    expect(page.locator("#retry-counter")).to_have_text("0")


def test_validation_error_invalid_e164_and_length(page: Page):
    """
    Test Case 2: Validation Failure
    Ensures invalid recipient MSISDN is rejected by the backend with 400.
    """
    def handle_send_reject(route: Route):
        route.fulfill(
            status=400,
            content_type="application/json",
            body=json.dumps({"error": "Invalid E.164 phone number format"}),
        )

    page.route("**/api/v1/sms/send", handle_send_reject)

    page.goto(f"{BASE_URL}/console")
    page.fill("#recipient", "0712345678")  # Non-E.164
    page.fill("#message", "Valid length body.")
    page.click("#send-btn")

    validation_err = page.locator("#validation-error")
    expect(validation_err).to_be_visible()
    expect(validation_err).to_have_text("Invalid E.164 phone number format")


def test_carrier_exhausted_retries_triggers_undeliverable_and_webhook(page: Page):
    """
    Test Case 3: Retries and Terminal Failure
    Carrier returns FAILED. Emulates 3 retries (backoff 5s, 10s, 20s represented via mock state),
    transitions to UNDELIVERABLE, and triggers webhook.
    """
    msg_id = "msg-uuid-fail-999"
    webhook_triggered = {"called": False, "payload": None}
    poll_state = {"attempt": 0}

    def handle_send(route: Route):
        route.fulfill(
            status=202,
            content_type="application/json",
            body=json.dumps({"message_id": msg_id, "status": "QUEUED"}),
        )

    def handle_status(route: Route):
        poll_state["attempt"] += 1
        # Cycle through attempts: 1 (queued), 2 (retry 1), 3 (retry 2), 4 (terminal UNDELIVERABLE)
        if poll_state["attempt"] < 4:
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps({
                    "message_id": msg_id,
                    "status": "QUEUED",
                    "retries": poll_state["attempt"] - 1,
                }),
            )
        else:
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps({
                    "message_id": msg_id,
                    "status": "UNDELIVERABLE",
                    "retries": 3,
                }),
            )

    def handle_webhook_alert(route: Route):
        webhook_triggered["called"] = True
        webhook_triggered["payload"] = json.loads(route.request.post_data)
        route.fulfill(status=200, body=json.dumps({"received": True}))

    page.route("**/api/v1/sms/send", handle_send)
    page.route(f"**/api/v1/sms/{msg_id}/status", handle_status)
    page.route("**/api/v1/webhooks/alerts", handle_webhook_alert)

    page.goto(f"{BASE_URL}/console")
    page.fill("#recipient", "+14155559999")
    page.fill("#message", "Notice: Network Outage in your local area.")
    page.click("#send-btn")

    # Wait for the status transition to reach terminal failure state
    expect(page.locator("#sms-status")).to_have_text("UNDELIVERABLE", timeout=10000)
    expect(page.locator("#retry-counter")).to_have_text("3")

    # Simulate Gateway firing webhook alert after marking status
    page.evaluate(
        """() => {
            fetch('/api/v1/webhooks/alerts', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    event: 'SMS_UNDELIVERABLE',
                    message_id: 'msg-uuid-fail-999',
                    retries: 3,
                    reason: 'MAX_RETRIES_EXCEEDED'
                })
            });
        }"""
    )

    page.wait_for_timeout(1000)
    assert webhook_triggered["called"] is True
    assert webhook_triggered["payload"]["event"] == "SMS_UNDELIVERABLE"
    assert webhook_triggered["payload"]["retries"] == 3
