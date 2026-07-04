"""
Guardian Angel — Data Models

Pydantic models for API request/response validation and structured data.
These models define the schema for users, consent records, alerts, audit logs,
and risk decisions throughout the application.
"""

from __future__ import annotations

import json
from datetime import datetime
from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field


# ── Enums ────────────────────────────────────────────────────────────────────


class UserRole(str, Enum):
    ELDER = "elder"
    FAMILY = "family"


class RiskTier(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ActionType(str, Enum):
    LOG_ONLY = "log_only"
    WARN_ELDER = "warn_elder"
    ALERT_FAMILY = "alert_family"
    PAUSE_TRANSACTION = "pause_transaction"


# ── User Models ──────────────────────────────────────────────────────────────


class UserCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="User's display name")
    role: UserRole = Field(..., description="Either 'elder' or 'family'")
    pin: str = Field(..., min_length=4, max_length=6, description="PIN for authentication")


class UserLogin(BaseModel):
    name: str
    pin: str


class UserResponse(BaseModel):
    id: str
    name: str
    role: UserRole
    created_at: str


# ── Consent Models ───────────────────────────────────────────────────────────


class ConsentGrant(BaseModel):
    """Request body when an elder grants consent."""
    authorized_family_ids: list[str] = Field(
        ...,
        min_length=1,
        description="List of family member user IDs authorized to receive alerts",
    )


class ConsentStatus(BaseModel):
    """Response showing current consent state for an elder."""
    elder_id: str
    active: bool
    revoked: bool
    authorized_family_ids: list[str]
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class InviteCodeResponse(BaseModel):
    """Response when an elder generates an invite code."""
    code: str
    expires_at: str


class InviteRedeem(BaseModel):
    """Request body when a family member redeems an invite code."""
    code: str


# ── Risk Decision Models ────────────────────────────────────────────────────


class RiskDecision(BaseModel):
    """
    Structured output from the orchestrator agent.
    Every decision must include human-readable reasons — a bare score is never acceptable.
    """
    risk_score: int = Field(..., ge=0, le=100, description="Combined risk score 0-100")
    tier: RiskTier = Field(..., description="Risk tier: low, medium, or high")
    reasons: list[str] = Field(
        ...,
        min_length=1,
        description="Concrete, human-readable evidence for the score. Never empty.",
    )
    action: ActionType = Field(..., description="Action taken based on the risk tier")
    caller_verification_score: Optional[int] = Field(
        None, ge=0, le=100, description="Score from caller verification sub-analysis"
    )
    scam_pattern_score: Optional[int] = Field(
        None, ge=0, le=100, description="Score from scam pattern matching sub-analysis"
    )
    urgency_pressure_score: Optional[int] = Field(
        None, ge=0, le=100, description="Score from urgency/pressure detection sub-analysis"
    )
    matched_phrases: Optional[list[str]] = Field(
        None, description="Specific phrases from the transcript that triggered matches"
    )
    transaction_flagged: bool = Field(
        default=False, description="Whether a financial transaction was detected and flagged"
    )


# ── Alert Models ─────────────────────────────────────────────────────────────


class AlertResponse(BaseModel):
    """Alert as seen by both elder and family dashboards."""
    id: str
    elder_id: str
    elder_name: Optional[str] = None
    risk_score: int
    tier: RiskTier
    reasons: list[str]
    action_taken: ActionType
    summary_text: str
    caller_number: Optional[str] = None
    created_at: str


class AlertDetail(AlertResponse):
    """Extended alert detail with sub-scores."""
    caller_verification_score: Optional[int] = None
    scam_pattern_score: Optional[int] = None
    urgency_pressure_score: Optional[int] = None
    matched_phrases: Optional[list[str]] = None
    transaction_flagged: bool = False


# ── Audit Log Models ────────────────────────────────────────────────────────


class AuditLogEntry(BaseModel):
    """Immutable audit trail entry. Append-only — never updated or deleted."""
    id: str
    elder_id: str
    event_type: str
    risk_decision: Optional[dict] = None
    metadata: Optional[dict] = None
    timestamp: str


# ── Call/Text Event Models ──────────────────────────────────────────────────


class CallEvent(BaseModel):
    """Incoming call transcript event for analysis."""
    elder_id: str = Field(..., description="ID of the elder receiving the call")
    caller_number: Optional[str] = Field(None, description="Caller's phone number if available")
    claimed_identity: Optional[str] = Field(
        None, description="Who the caller claims to be, e.g. 'State Bank fraud department'"
    )
    transcript: str = Field(
        ...,
        min_length=1,
        description="Rolling transcript of the call (text, not audio)",
    )
    has_transaction: bool = Field(
        default=False,
        description="Whether a financial transaction is mentioned or attempted",
    )
    transaction_details: Optional[dict] = Field(
        None,
        description="Transaction details if has_transaction is True",
    )


class TextMessageEvent(BaseModel):
    """Incoming text/SMS message event for analysis."""
    elder_id: str
    sender_number: Optional[str] = None
    message_text: str = Field(..., min_length=1)


# ── Family Alert Payload ────────────────────────────────────────────────────


class FamilyAlertPayload(BaseModel):
    """
    What gets sent to family members. Intentionally limited —
    contains only tier, reasons, and a summary. NEVER the raw transcript.
    """
    alert_id: str
    elder_id: str
    elder_name: str
    tier: RiskTier
    reasons: list[str]
    summary: str
    action_taken: ActionType
    timestamp: str
