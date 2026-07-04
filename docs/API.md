# Guardian Angel — API Reference

## Base URL

```
http://localhost:8000/api
```

All endpoints require JWT authentication unless noted otherwise.

---

## Authentication

### `POST /api/auth/register`

Register a new user account.

**Auth Required**: No

**Request Body**:
```json
{
  "username": "Margaret Johnson",
  "role": "elder",
  "password": "secure_password"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `username` | string | ✅ | Display name |
| `role` | string | ✅ | `"elder"` or `"family"` |
| `password` | string | ✅ | Account password |

**Response** `200`:
```json
{
  "token": "eyJ...",
  "user": {
    "id": "uuid-here",
    "name": "Margaret Johnson",
    "role": "elder"
  }
}
```

---

### `POST /api/auth/login`

Authenticate and receive a JWT token.

**Auth Required**: No

**Request Body**:
```json
{
  "username": "Margaret Johnson",
  "password": "secure_password"
}
```

**Response** `200`:
```json
{
  "token": "eyJ...",
  "user": {
    "id": "uuid-here",
    "name": "Margaret Johnson",
    "role": "elder"
  }
}
```

---

### `GET /api/auth/me`

Get current authenticated user profile.

**Auth Required**: Yes

**Response** `200`:
```json
{
  "id": "uuid-here",
  "name": "Margaret Johnson",
  "role": "elder"
}
```

---

## Consent

### `POST /api/consent/grant`

Grant or update consent. **Elder only.**

**Auth Required**: Yes (elder role)

**Request Body**:
```json
{
  "authorized_family_ids": ["family-uuid-1", "family-uuid-2"]
}
```

**Response** `200`:
```json
{
  "id": "consent-uuid",
  "elder_id": "elder-uuid",
  "active": true,
  "revoked": false,
  "authorized_family_ids": ["family-uuid-1"],
  "granted_at": "2024-01-15T10:30:00Z"
}
```

---

### `POST /api/consent/revoke`

Instantly revoke all consent. **Elder only.**

**Auth Required**: Yes (elder role)

**Response** `200`:
```json
{
  "status": "revoked",
  "revoked_at": "2024-01-15T12:00:00Z"
}
```

---

### `GET /api/consent/status`

Get current consent status for the authenticated elder.

**Auth Required**: Yes (elder role)

**Response** `200`:
```json
{
  "id": "consent-uuid",
  "elder_id": "elder-uuid",
  "active": true,
  "revoked": false,
  "authorized_family_ids": ["family-uuid-1"],
  "granted_at": "2024-01-15T10:30:00Z",
  "revoked_at": null
}
```

---

### `POST /api/consent/generate-invite`

Generate a one-time invite code for linking a family member. **Elder only.**

**Auth Required**: Yes (elder role)

**Response** `200`:
```json
{
  "code": "A3B7K9",
  "expires_at": "2024-01-16T10:30:00Z"
}
```

---

### `POST /api/consent/redeem-invite`

Redeem an invite code to link with an elder. **Family only.**

**Auth Required**: Yes (family role)

**Request Body**:
```json
{
  "code": "A3B7K9"
}
```

**Response** `200`:
```json
{
  "success": true,
  "elder_id": "elder-uuid",
  "elder_name": "Margaret Johnson"
}
```

---

### `GET /api/consent/linked-elders`

Get list of elders who have authorized this family member. **Family only.**

**Auth Required**: Yes (family role)

**Response** `200`:
```json
[
  {
    "id": "elder-uuid",
    "name": "Margaret Johnson",
    "shield_active": true
  }
]
```

---

## Alerts

### `GET /api/alerts/elder/{elder_id}`

Get all alerts for a specific elder. **Elder only (own alerts).**

**Auth Required**: Yes (elder role, own ID)

**Response** `200`:
```json
[
  {
    "id": "alert-uuid",
    "elder_id": "elder-uuid",
    "call_id": "call-uuid",
    "tier": "high",
    "summary_text": "IRS impersonation scam detected...",
    "reasons": [
      "Government impersonation",
      "Gift card payment demanded",
      "Arrest threat used"
    ],
    "family_notified": true,
    "created_at": "2024-01-15T10:35:00Z"
  }
]
```

---

### `GET /api/alerts/family/{family_id}`

Get alerts for all elders who have authorized this family member. **Family only.**

**Auth Required**: Yes (family role, own ID)

**Response**: Same format as elder alerts endpoint.

---

### `GET /api/alerts/{alert_id}`

Get detailed info for a single alert. Authorization checked against role.

**Auth Required**: Yes

**Response** `200`:
```json
{
  "id": "alert-uuid",
  "elder_id": "elder-uuid",
  "call_id": "call-uuid",
  "tier": "high",
  "summary_text": "IRS impersonation scam detected...",
  "reasons": ["..."],
  "family_notified": true,
  "created_at": "2024-01-15T10:35:00Z"
}
```

---

## Events

### `POST /api/events/call-chunk`

Submit a real-time call transcript chunk for analysis.

**Auth Required**: Yes

**Request Body**:
```json
{
  "call_id": "call-uuid",
  "elder_id": "elder-uuid",
  "caller_number": "+18005551234",
  "caller_claimed_identity": "IRS",
  "speaker": "caller",
  "text": "You owe us $4,500 in back taxes...",
  "chunk_index": 0,
  "is_final_chunk": false
}
```

**Response** `200`:
```json
{
  "processed": true,
  "alert_generated": true,
  "risk_tier": "high",
  "alert_id": "alert-uuid"
}
```

---

## Audit

### `GET /api/audit/log`

Retrieve the audit log. **Elder only (own log) or system.**

**Auth Required**: Yes

**Query Parameters**:
| Param | Type | Description |
|-------|------|-------------|
| `limit` | int | Max entries to return (default 50) |
| `offset` | int | Pagination offset |

**Response** `200`:
```json
[
  {
    "id": "log-uuid",
    "timestamp": "2024-01-15T10:30:00Z",
    "event_type": "consent_granted",
    "elder_id": "elder-uuid",
    "details": "Consent granted with 1 family member authorized",
    "actor": "elder-uuid"
  }
]
```

---

## Error Responses

All endpoints return errors in this format:

```json
{
  "detail": "Human-readable error message"
}
```

| Status Code | Meaning |
|-------------|---------|
| `400` | Bad request (invalid input) |
| `401` | Unauthorized (missing/invalid token) |
| `403` | Forbidden (insufficient permissions) |
| `404` | Resource not found |
| `409` | Conflict (e.g., user already exists) |
| `500` | Internal server error |
