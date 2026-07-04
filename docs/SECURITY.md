# Guardian Angel — Security Model

## Overview

Guardian Angel processes sensitive personal data (phone call transcriptions) and must uphold the highest standards of privacy and security. This document outlines the security model, privacy guarantees, and threat mitigations.

---

## Core Privacy Guarantees

### 1. No Audio Recording
- Guardian Angel **never records, stores, or transmits audio**.
- The telephony layer (Twilio Media Streams) converts audio to text via Speech-to-Text in real-time.
- Only text transcription is processed; audio payloads are discarded immediately.

### 2. No Transcript Storage
- Raw call transcripts are **not stored** in the database.
- The AI pipeline processes transcript chunks in memory and generates structured alerts.
- Once an alert is generated, the raw text is discarded.
- Only the alert summary, risk tier, and detected patterns are persisted.

### 3. Family Sees Summaries Only
- Family members **never** see raw transcript text.
- The `family_alert_server` MCP tool generates a short summary (2-3 sentences max).
- The summary describes the type of threat detected, not the content of the conversation.

### 4. Elder Sees Everything
- The elder can see all alerts that were shared with family.
- There are **no hidden alerts** — the elder dashboard and family dashboard show the same alert set.
- This prevents the system from being used as covert surveillance.

---

## Consent Model

### Three-Party Handshake
1. **Elder grants consent** on their own device, using their own credentials.
2. **Elder chooses** which family members receive alerts (via invite codes).
3. **Family member accepts** by redeeming the invite code.

### Consent Gate Enforcement
- The `ConsentGate` is a hard code-level block, not a configuration flag.
- Every event processing function calls `ConsentGate.check(elder_id)` before executing.
- If consent is not active, the function raises `ConsentDeniedError` and the event is silently dropped.
- No amount of API manipulation can bypass this — it is enforced in the application layer, not the routing layer.

### Revocation
- The elder can revoke consent at any time with a single tap.
- Revocation is **immediate**: all processing stops, no new alerts are generated.
- Revocation also triggers deletion of pending alerts from the family feed.
- The revocation event is logged in the immutable audit trail.

---

## Authentication & Authorization

### JWT Tokens
- All API endpoints require JWT authentication (except `/api/auth/login` and `/api/auth/register`).
- Tokens are short-lived (configurable, default 24 hours).
- Tokens contain: `user_id`, `role`, `exp`.

### Role-Based Access Control
| Endpoint | Elder | Family | System |
|----------|-------|--------|--------|
| `GET /api/alerts/elder/{id}` | Own only | ❌ | ✅ |
| `GET /api/alerts/family/{id}` | ❌ | Own only | ✅ |
| `POST /api/consent/grant` | ✅ | ❌ | ❌ |
| `POST /api/consent/revoke` | ✅ | ❌ | ❌ |
| `GET /api/audit/log` | Own only | ❌ | ✅ |
| `POST /api/events/call-chunk` | ✅ | ❌ | ✅ |

---

## Audit Trail

### Append-Only Log
- All significant system events are written to the `audit_log` table.
- This table is **append-only** — rows are never updated or deleted.
- Logged events include:
  - Consent granted / revoked
  - Alert created / dismissed
  - Family member linked / unlinked
  - Login / logout
  - Shield toggled on / off
  - System errors

### Tamper Detection
- Each audit log entry includes a SHA-256 hash of the previous entry, creating a chain.
- Any modification to historical entries would break the chain and be detectable.

---

## Threat Model

### Threats Mitigated

| Threat | Mitigation |
|--------|------------|
| Family member uses system as surveillance | Elder sees everything; no hidden alerts; revocation always available |
| Unauthorized access to alerts | JWT auth + role-based access control |
| API manipulation to bypass consent | ConsentGate is code-level, not routing-level |
| Transcript leakage to family | family_alert_server only outputs summaries |
| Data persistence of sensitive calls | Raw transcripts are never stored; only alert summaries persisted |
| Coerced consent (elder pressured) | Voice/PIN confirmation during onboarding; visible revocation button |
| Audit log tampering | Append-only with hash chain |

### Known Limitations
- **STT accuracy**: Speech-to-text may misinterpret words, potentially causing false positives or false negatives.
- **Pattern evasion**: Sophisticated scammers may use language that evades pattern detection.
- **Coercion detection**: The system cannot detect if an elder is being physically coerced into maintaining consent.
- **Offline access**: If the elder's device loses connectivity, real-time protection is unavailable.

---

## Data Retention

| Data Type | Retention Policy |
|-----------|-----------------|
| User accounts | Until deleted by user |
| Consent records | Permanent (audit requirement) |
| Alert summaries | 90 days (configurable) |
| Raw transcripts | **Never stored** |
| Audio recordings | **Never captured** |
| Audit log | Permanent |

---

## Compliance Notes

- The system is designed with GDPR and CCPA principles in mind.
- Data minimization: only the minimum necessary data is collected and stored.
- Right to erasure: users can delete their accounts; consent records are anonymized.
- Consent is explicit, informed, and revocable.
