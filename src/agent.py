import os
import re
from google import genai
from google.genai import types

# Initialize Google GenAI Client (automatically pulls GEMINI_API_KEY from environment variables)
client = genai.Client()

SAMPLE_FEATURE_DESCRIPTION = """
Feature: Telecom SMS Delivery Confirmation Flow
Description:
The SMS Delivery Gateway allows users to send outbound messages and tracks delivery statuses.
When a user submits an SMS payload with sender ID, recipient number, and text message body:
1. The system validates payload formatting (E.164 phone number format, max 160 chars for single SMS).
2. The SMS status is set to 'QUEUED' and dispatched to the telecom carrier network.
3. Upon receiving a Delivery Receipt (DLR) callback from the carrier within 30 seconds, status updates to 'DELIVERED'.
4. If a 'FAILED' status is returned or timeout occurs (>30s), the gateway retries delivery up to 3 times with exponential backoff (5s, 10s, 20s).
5. After 3 failed attempts, status is permanently set to 'UNDELIVERABLE' and a webhook alert is triggered.
"""

SYSTEM_PROMPT = """
You are an expert Telecom QA Automation Engineer specializing in BDD testing, Playwright automation, and Test Coverage Analysis.
Your task is to analyze a given Telecom Feature Description and generate three strict output sections wrapped in distinct markdown code blocks:

SECTION 1: GHERKIN SCENARIOS
- Generate clean, standard BDD syntax (Feature, Scenario, Given, When, Then).
- Cover happy path, alternate flows, retry mechanisms, and edge cases.
- Wrap this code block in ```gherkin ... ```

SECTION 2: PLAYWRIGHT TEST SCRIPT
- Write a fully runnable Python Playwright test script using pytest-playwright or standard Playwright async/sync API.
- Mock network endpoints or callbacks where appropriate to simulate success, timeout, and failure states.
- Include assertions for DOM elements, API responses, or status updates.
- Wrap this code block in ```python ... ```

SECTION 3: COVERAGE GAP REPORT
- Produce a detailed Markdown report identifying untested edge cases.
- Explicitly flag: Boundary values (e.g., character limits, special unicode chars), Timeout/Retry paths, Malformed payloads, and Network edge cases (gateway drops, DLR race conditions).
- Wrap this section in ```markdown ... ```
"""

def run_telco_copilot(feature_text: str, output_dir: str = "generated_outputs"):
    os.makedirs(output_dir, exist_ok=True)
    print("🤖 TelcoQA Copilot analyzing feature description using Google Gemini...\n")
    
    response = client.models.generate_content(
        model="gemini-3.8-flash",
        contents=f"Feature Description:\n{feature_text}",
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            temperature=0.2
        )
    )
    
    raw_content = response.text
    
    # Extract blocks using Regex
    gherkin_match = re.search(r"```gherkin\n(.*?)```", raw_content, re.DOTALL)
    python_match = re.search(r"```python\n(.*?)```", raw_content, re.DOTALL)
    markdown_match = re.search(r"```markdown\n(.*?)```", raw_content, re.DOTALL)

    if gherkin_match:
        with open(os.path.join(output_dir, "sms_delivery.feature"), "w") as f:
            f.write(gherkin_match.group(1).strip())
        print("✅ Generated Gherkin Test Cases: generated_outputs/sms_delivery.feature")

    if python_match:
        with open(os.path.join(output_dir, "test_sms_delivery.py"), "w") as f:
            f.write(python_match.group(1).strip())
        print("✅ Generated Playwright Test Script: generated_outputs/test_sms_delivery.py")

    if markdown_match:
        with open(os.path.join(output_dir, "coverage_gap_report.md"), "w") as f:
            f.write(markdown_match.group(1).strip())
        print("✅ Generated Coverage-Gap Report: generated_outputs/coverage_gap_report.md")

    print("\n🎉 Copilot execution completed successfully!")

if __name__ == "__main__":
    run_telco_copilot(SAMPLE_FEATURE_DESCRIPTION)
