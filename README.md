# 🛡️ Guardian Angel

**Real-Time Scam & Fraud Shield for Elderly Family Members**

Guardian Angel is an AI-powered protection system that monitors phone calls in real-time (as text transcription, never audio) to detect scam patterns, alert family members, and block fraudulent transactions — all with explicit elder consent and full transparency.

---

## 🎯 Key Principles

- **Elder-first consent**: The elder controls everything. They grant, pause, and revoke consent at any time with a single tap.
- **No surveillance**: Guardian Angel never records audio. It processes call text in real-time and discards it. Family members only see summaries, never full transcripts.
- **Transparency**: The elder sees everything that is shared with their family. There are no hidden alerts.
- **Immediate control**: The "Revoke Consent" button is always visible, always one tap, and instantly stops all processing.

---

## 🏗️ Architecture

```
┌─────────────┐    ┌──────────────────┐    ┌─────────────────────┐
│  Telephony   │───▶│  FastAPI Backend  │───▶│  AI Agent Pipeline  │
│  (Twilio)    │    │  (Event Router)   │    │  (Antigravity SDK)  │
└─────────────┘    └──────────────────┘    └─────────────────────┘
                            │                        │
                   ┌────────┴────────┐      ┌────────┴────────┐
                   │  Consent Gate   │      │   MCP Servers   │
                   │  (Hard Block)   │      │  (Tool Layer)   │
                   └─────────────────┘      └─────────────────┘
                            │                        │
                   ┌────────┴────────┐      ┌────────┴────────┐
                   │   SQLite DB     │      │  Scam Patterns  │
                   │  (Append-only   │      │  Caller ID      │
                   │   Audit Log)    │      │  Bank Txn Guard │
                   └─────────────────┘      │  Family Alerts  │
                                            └─────────────────┘
```

### Components

| Component | Path | Description |
|-----------|------|-------------|
| **Backend** | `backend/` | FastAPI server with auth, consent, events, alerts, and audit routers |
| **Consent Gate** | `consent/` | Hard code-level block — no event processes without valid consent |
| **MCP Servers** | `mcp_servers/` | Scam pattern matching, caller ID, bank transaction guard, family alerts |
| **AI Orchestrator** | `agents/` | Google Antigravity SDK agent with OpenRouter proxy |
| **Database** | `database/` | Async SQLite with append-only audit logging |
| **Frontend** | `frontend/` | Web UI with elder dashboard, family dashboard, and onboarding |
| **Telephony** | `telephony/` | Twilio webhook handlers and Media Streams WebSocket |
| **Demo** | `demo/` | Sample call data, replay script, and database seeder |

---

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Docker & Docker Compose (optional)
- An [OpenRouter API key](https://openrouter.ai/)

### 1. Clone & Configure

```bash
git clone <repo-url> guardian-angel
cd guardian-angel
cp .env.example .env
# Edit .env and add your OPENROUTER_API_KEY
```

### 2. Install Dependencies

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Seed Demo Data

```bash
python demo/seed_data.py
```

### 4. Run the Server

```bash
uvicorn backend.main:app --reload --port 8000
```

### 5. Open the Web UI

Navigate to `http://localhost:8000` in your browser.

**Demo accounts** (created by seed script):
- **Elder**: Margaret Johnson
- **Family**: Sarah Johnson

### 6. Run Demo Replay (Optional)

```bash
python demo/replay_demo.py --delay 1.5
```

---

## 🐳 Docker

```bash
docker-compose up --build
```

The app will be available at `http://localhost:8000`.

---

## 📁 Project Structure

```
guardian-angel/
├── agents/                  # AI orchestrator & prompts
│   ├── orchestrator.py      # Antigravity SDK agent
│   ├── openrouter_proxy.py  # OpenRouter ↔ Gemini translation
│   └── prompts/             # System prompts for each analysis role
├── backend/                 # FastAPI application
│   ├── main.py              # App entry point
│   └── routers/             # API route handlers
├── consent/                 # Consent enforcement layer
│   └── consent_gate.py      # Hard consent block
├── database/                # Data persistence
│   ├── db.py                # Async SQLite operations
│   └── models.py            # Pydantic models
├── demo/                    # Demo & testing utilities
│   ├── sample_calls.json    # Sample scam call transcripts
│   ├── replay_demo.py       # API replay script
│   └── seed_data.py         # Database seeder
├── frontend/                # Web UI
│   ├── index.html           # Login/register
│   ├── onboarding.html      # Consent onboarding flow
│   ├── elder-dashboard.html # Elder's protected dashboard
│   ├── family-dashboard.html# Family member dashboard
│   ├── css/styles.css       # Design system
│   └── js/                  # Frontend controllers
├── mcp_servers/             # MCP tool servers
├── telephony/               # Twilio integration
├── docs/                    # Documentation
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── .env.example
```

---

## 🔒 Security & Privacy

- **No audio recording**: Only text transcription is processed, never stored long-term.
- **Consent-gated processing**: Every operation checks the `ConsentGate` before executing.
- **Append-only audit log**: All system actions are logged immutably for transparency.
- **Family sees summaries only**: Raw transcripts are never exposed to family members.
- **JWT authentication**: All API endpoints require authentication.
- **Instant revocation**: Elder can revoke consent with one tap, immediately stopping all processing.

See [docs/SECURITY.md](docs/SECURITY.md) for the full security model.

---

## 📖 Documentation

- [Architecture Guide](docs/ARCHITECTURE.md) — System design and data flow
- [Security Model](docs/SECURITY.md) — Privacy guarantees and threat model
- [API Reference](docs/API.md) — Full endpoint documentation
- [Demo Guide](docs/DEMO.md) — Running the demo and testing

---

## 📄 License

This project is for educational and demonstration purposes.
