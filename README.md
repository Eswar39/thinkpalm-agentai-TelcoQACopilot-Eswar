# TelcoQA Copilot 🤖

An autonomous Agentic AI tool for telecom software testing. TelcoQA Copilot converts raw Telecom Feature Descriptions into BDD Gherkin test scenarios, automated Playwright execution scripts, and test coverage analysis reports using Google Gemini (`gemini-3.8-flash`).

---

## 🌟 Key Features

- **Automated Gherkin Generation**: Translates complex telecom system logic (retries, timeouts, E.164 validations) into standard BDD Given/When/Then scenarios.
- **Executable Playwright Test Suite**: Generates Python-based Playwright tests configured for `pytest` execution.
- **Coverage Gap Analysis**: Automatically scans specifications for edge cases, character limits, backoff intervals, and gateway race conditions.
- **Agentic File Processing**: Uses regex-based parsing to write structured test deliverables directly into local directories (`generated_outputs/`).

---

## 📁 Repository Structure

```text
.
├── src/
│   ├── agent.py            # Core agent logic and Gemini API integration
│   └── requirements.txt    # Python package dependencies
├── generated_outputs/      # Output directory produced during agent execution
│   ├── sms_delivery.feature
│   ├── test_sms_delivery.py
│   └── coverage_gap_report.md
└── README.md               # Project documentation
