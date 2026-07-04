# Guardian Angel — Demo Guide

## Overview

The demo system lets you experience Guardian Angel's scam detection pipeline without a live phone connection. It replays pre-recorded call transcripts through the API and shows alerts appearing in real-time on the dashboards.

---

## Setup

### 1. Start the Backend

```bash
source venv/bin/activate
uvicorn backend.main:app --reload --port 8000
```

### 2. Seed Demo Data

```bash
python demo/seed_data.py
```

This creates:
- **Elder account**: Margaret Johnson
- **Family account**: Sarah Johnson
- **4 pre-seeded alerts** of varying risk levels
- **Consent record** linking Margaret → Sarah

### 3. Open the Web UI

Navigate to `http://localhost:8000` and log in with either demo account.

---

## Running the Replay Demo

The replay script sends sample call transcripts through the event API, simulating real phone calls:

```bash
python demo/replay_demo.py
```

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `--base-url` | `http://127.0.0.1:8000` | Backend API URL |
| `--delay` | `1.5` | Seconds between transcript chunks |

### What Happens

1. The script registers/logs in as the demo elder
2. Grants consent for monitoring
3. Replays 5 sample calls, sending transcript chunks one at a time
4. For each chunk, the backend:
   - Validates consent via ConsentGate
   - Runs the AI analysis pipeline
   - Generates alerts if scam patterns detected
   - Dispatches family notifications for medium/high risk
5. Prints a final summary of all generated alerts

---

## Sample Call Scenarios

| # | Scenario | Expected Risk | Key Patterns |
|---|----------|---------------|--------------|
| 1 | IRS impersonation with arrest threat | 🔴 HIGH | Government impersonation, gift card demand, arrest threat |
| 2 | Bank fraud — credential harvesting | 🔴 HIGH | Bank impersonation, SSN request, urgency pressure |
| 3 | Tech support scam — remote access | 🔴 HIGH | Tech support impersonation, remote access, wire transfer |
| 4 | Doctor's office appointment reminder | 🟢 LOW | Legitimate call (negative test) |
| 5 | Grandparent scam — bail money | 🔴 HIGH | Grandparent impersonation, secrecy demand, wire transfer |

---

## Watching Real-Time Alerts

1. Open the **Elder Dashboard** in one browser tab
2. Open the **Family Dashboard** in another tab (log in as Sarah)
3. Run the replay script
4. Watch alerts appear in real-time on both dashboards
5. The Elder Dashboard shows a pulsing red warning banner for active high-risk calls
6. The Family Dashboard shows the incident banner with a "Call Now" button

---

## Testing the Consent Flow

1. Log in as **Margaret Johnson** (elder)
2. Navigate to the Elder Dashboard
3. Toggle the Shield off → alerts should stop generating
4. Toggle the Shield back on → alerts resume
5. Click "Revoke Consent Immediately" → all processing stops, session ends

---

## Adding Custom Test Calls

Edit `demo/sample_calls.json` to add your own scenarios. Each call needs:

```json
{
  "call_id": "unique-id",
  "elder_id": "elder-demo-001",
  "caller_number": "+18005551234",
  "caller_claimed_identity": "Organization Name",
  "transcript_chunks": [
    { "speaker": "caller", "text": "..." },
    { "speaker": "elder", "text": "..." }
  ],
  "expected_risk_tier": "high",
  "expected_patterns": ["pattern_name"],
  "description": "Short description of the scenario"
}
```
