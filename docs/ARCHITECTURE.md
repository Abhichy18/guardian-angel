# Guardian Angel — Architecture Guide

## System Overview

Guardian Angel is a multi-layered real-time protection system designed to detect phone scams targeting elderly family members. The system processes call transcriptions (never audio) through an AI analysis pipeline and generates alerts when scam patterns are detected.

---

## Data Flow

```
Phone Call
    │
    ▼
┌─────────────────────────────────┐
│  Telephony Layer (Twilio)       │
│  - Receives incoming calls      │
│  - Streams audio via WebSocket  │
│  - STT transcription            │
└────────────┬────────────────────┘
             │ Transcript chunks
             ▼
┌─────────────────────────────────┐
│  FastAPI Event Router           │
│  POST /api/events/call-chunk    │
│  - Validates JWT auth           │
│  - Rate limiting                │
└────────────┬────────────────────┘
             │
             ▼
┌─────────────────────────────────┐
│  Consent Gate (HARD BLOCK)      │
│  - Checks elder has active      │
│    consent in database          │
│  - If no consent → DROP event   │
│  - If revoked → DROP event      │
│  - Zero processing without      │
│    explicit consent              │
└────────────┬────────────────────┘
             │ Consent verified
             ▼
┌─────────────────────────────────┐
│  AI Orchestrator                │
│  (Google Antigravity SDK)       │
│  - Routes to analysis agents    │
│  - Aggregates risk scores       │
│  - Determines alert tier        │
└────────────┬────────────────────┘
             │ Tool calls
             ▼
┌─────────────────────────────────┐
│  MCP Tool Servers               │
│  ┌───────────────────────┐      │
│  │ Scam Pattern Matcher  │      │
│  │ (regex + heuristics)  │      │
│  ├───────────────────────┤      │
│  │ Caller ID Verifier    │      │
│  │ (number lookup)       │      │
│  ├───────────────────────┤      │
│  │ Bank Transaction      │      │
│  │ Guardrail (risk score)│      │
│  ├───────────────────────┤      │
│  │ Family Alert          │      │
│  │ Dispatcher (filtered) │      │
│  └───────────────────────┘      │
└────────────┬────────────────────┘
             │ Results
             ▼
┌─────────────────────────────────┐
│  Alert Generator                │
│  - Compiles risk tier           │
│  - Generates summary text       │
│  - Stores alert in DB           │
│  - Dispatches family alert      │
│    (summary only, never raw     │
│     transcript)                 │
└────────────┬────────────────────┘
             │
     ┌───────┴───────┐
     ▼               ▼
┌──────────┐  ┌──────────────┐
│ Elder    │  │ Family       │
│ Dashboard│  │ Dashboard    │
│ (sees    │  │ (sees        │
│  everything)│  summaries    │
│          │  │  only)       │
└──────────┘  └──────────────┘
```

---

## Component Details

### 1. Consent Gate (`consent/consent_gate.py`)

The Consent Gate is the single most important architectural decision. It is a **hard code-level enforcement** mechanism, not a policy or configuration flag.

**Rules:**
- Every function that processes call data must call `ConsentGate.check()` first
- If consent is not active, the function raises `ConsentDeniedError` and the event is dropped
- The elder can revoke consent at any time; revocation is instant and irrevocable for that session
- All consent changes are logged in the append-only audit trail

### 2. MCP Servers (`mcp_servers/`)

Each MCP server is a standalone micro-service exposed via stdio protocol:

| Server | Function | Tools Exposed |
|--------|----------|---------------|
| `scam_pattern_server` | Pattern matching against known scam scripts | `analyze_patterns`, `check_keywords` |
| `caller_id_server` | Phone number lookup and institution verification | `lookup_number`, `verify_institution` |
| `bank_transaction_server` | Transaction risk scoring and emergency pause | `score_risk`, `pause_transaction` |
| `family_alert_server` | Alert dispatch with transcript filtering | `send_alert`, `format_summary` |

### 3. AI Orchestrator (`agents/orchestrator.py`)

Uses the Google Antigravity SDK to coordinate analysis across MCP servers. The orchestrator:
1. Receives a transcript chunk
2. Calls scam pattern analysis tools
3. Calls caller ID verification tools
4. Aggregates results into a risk score
5. If risk exceeds threshold, generates an alert
6. If alert is generated, dispatches to family (summary only)

### 4. OpenRouter Proxy (`agents/openrouter_proxy.py`)

Bridges the Antigravity SDK (which expects Gemini/Vertex endpoints) to OpenRouter's API:
- Translates `Contents` format to OpenRouter's message format
- Maps `Tools` definitions to OpenRouter function calling schema
- Handles `responseMimeType` and structured output schemas

### 5. Database (`database/db.py`)

Async SQLite with the following tables:

| Table | Purpose | Retention |
|-------|---------|-----------|
| `users` | User accounts (elder/family) | Permanent |
| `consent_records` | Active consent state | Permanent (audit) |
| `alerts` | Generated scam alerts | 90 days default |
| `audit_log` | Append-only system event log | Permanent |

### 6. Frontend

Three distinct views, each designed for its audience:

- **Elder Dashboard**: Large text, high contrast, warm colors. Shield toggle, alert feed (sees everything), revoke consent button always visible.
- **Family Dashboard**: Dark theme, compact. Alert feed (summaries only), risk stats, linked elders management, invite code entry.
- **Onboarding**: Three-party handshake consent flow. Elder-led, plain language, no jargon.

---

## Security Boundaries

```
┌─────────────────────────────────────────────────┐
│                 Trust Boundary                   │
│                                                   │
│  Elder's Device        │  Family's Device          │
│  ┌─────────────────┐   │  ┌──────────────────┐    │
│  │ Full transcript  │   │  │ Summaries ONLY   │    │
│  │ visibility       │   │  │ No raw text      │    │
│  │ Consent controls │   │  │ No audio access  │    │
│  │ Revocation power │   │  │ Read-only alerts │    │
│  └─────────────────┘   │  └──────────────────┘    │
│                         │                           │
└─────────────────────────────────────────────────┘
```

---

## Deployment Model

- **Development**: `uvicorn` with hot-reload, SQLite file database
- **Production**: Docker container on Cloud Run, with PostgreSQL for persistence
- **Telephony**: Twilio phone number with Media Streams webhook
