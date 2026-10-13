
Coverage Gap & Risk Analysis Report: SMS Delivery Flow
1. High-Priority Gaps & Untested Edge Cases
Category	Gap Description	Severity	Risk Impact	Recommended Test Implementation
Boundary	GSM-7 vs. UCS-2 Character Encoding	Critical	Single emojis (e.g., 👋) drop single SMS max length from 160 chars to 70 chars.	Parameterized unit/integration tests with GSM 7-bit extended characters and Unicode multibyte characters to verify segmentation limit logic.
Boundary	E.164 Edge Cases	Medium	Handling maximum length (15 digits) vs minimum length (e.g., +688 Tuvalu) and alphanumeric Sender IDs (ALPHA_ID vs numeric shortcode).	Schema validation tests using ITU-T E.164 specification; test alpha sender ID compliance (max 11 chars).
Timeout / Retry	Carrier DLR Race Condition (At-the-wire)	High	DLR arrives exactly at $t = 30.05\text{ s}$$t = 30.05\text{ s}$ while the gateway retry worker has already scheduled attempt 2.	Concurrency integration tests checking mutex locks/state machines on the SMS status record during transition.
Timeout / Retry	Backoff Drift & Idempotency	High	Duplicate dispatch to carrier if backoff timer misfires, leading to duplicate SMS billing and multiple customer deliveries.	Verify idempotency key propagation across retry requests (5s, 10s, 20s backoff intervals).
Network Edge	Late/Out-of-Order DLR Arrival	Medium	A delayed DLR for attempt 1 arrives after attempt 2 has been dispatched.	Test state machine transition guard: ensure late DELIVERED cancels in-flight retries or late FAILED does not overwrite final DELIVERED.
Network Edge	Webhook Alert Destination Failure	High	Alert webhook endpoint for UNDELIVERABLE returns 5xx or drops connection.	Mock dead-letter queue (DLQ) behavior and secondary retry queue for outbound alerts.
2. Technical Edge Cases & Scenarios
A. Encoding & Payload Boundaries
UCS-2 Fallback Calculation:
Standard ASCII: 160 characters (GSM 7-bit).
Any character outside GSM 7 (e.g., Cyrillic, emoji, accents like á depending on carrier tables) triggers 70-character UCS-2 boundary.
Test Required: Verify body containing 71 characters with a single emoji is rejected if concatenation is disabled.
Zero-Width Characters & Malformed JSON:
Zero-width spaces (\u200B) and carriage returns (\r\n vs \n) altering byte lengths.
SQL injection / XSS payloads in sender ID and message text.
B. Timing & Race Conditions
Carrier Fast-Fail vs. Slow-Timeout Interleaving:
Attempt 1: Immediate carrier reject (REJECTED_INVALID_DESTINATION).
Behavior Question: Does the system immediately stop, or does it attempt all 3 retries? Non-transient errors (invalid number) should not retry, whereas transient errors (network congested) should.
Clock Skew on Distributed Gateway Workers:
Distributed worker nodes picking up retries prematurely before 5s/10s/20s backoff elapses due to NTP drift.
C. Downstream Webhook Edge Cases
Webhook Delivery Guarantees:
The spec mandates an alert webhook upon UNDELIVERABLE.
Test Needed: What happens if the customer webhook receiver takes >10 seconds to respond or returns HTTP 429 (Rate Limited)? Verify gateway exponential backoff on webhook dispatch independently of carrier retries.
