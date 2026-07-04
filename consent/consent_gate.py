"""
Guardian Angel — Consent Gate

Hard code-level enforcement of elder consent. This is NOT a soft prompt-level check —
it is a programmatic gate that refuses to process any call or text event unless the
elder has an active, unrevoked consent record in the database.

No prompt injection, no adversarial transcript, and no LLM hallucination can bypass this gate.
The check runs BEFORE any LLM or agent code is invoked.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from database.db import Database

logger = logging.getLogger(__name__)


class ConsentGate:
    """
    Refuses to process any call/text unless the elder has an active, unrevoked
    consent record. This is a hard code-level check, independent of the LLM's
    own judgment, so a prompt-injected transcript can never bypass consent.
    """

    def __init__(self, database: Database):
        self.database = database

    async def check(self, elder_id: str) -> bool:
        """
        Check whether the elder has active, unrevoked consent.

        Returns True only if:
        - A consent record exists for this elder_id
        - The record has active=True
        - The record has revoked=False

        Returns False in ALL other cases (no record, inactive, revoked).
        """
        record = await self.database.get_consent(elder_id)
        if record is None:
            logger.warning("No consent record found for elder %s", elder_id)
            return False

        has_consent = record.get("active", False) and not record.get("revoked", True)

        if not has_consent:
            logger.warning(
                "Consent check failed for elder %s: active=%s, revoked=%s",
                elder_id,
                record.get("active"),
                record.get("revoked"),
            )

        return has_consent

    async def get_authorized_family(self, elder_id: str) -> list[str]:
        """
        Get the list of family member IDs authorized to receive alerts.
        Returns empty list if no consent or consent is revoked.
        """
        if not await self.check(elder_id):
            return []

        record = await self.database.get_consent(elder_id)
        if record is None:
            return []

        return record.get("authorized_family_ids", [])

    async def process_event(self, elder_id: str, call_event: dict) -> dict:
        """
        Process a call/text event ONLY if the elder has active consent.

        This method is the single entry point for all event processing.
        It performs the consent check BEFORE any LLM/agent code runs.

        Args:
            elder_id: The elder's user ID.
            call_event: The call/text event data to analyze.

        Returns:
            The RiskDecision dict from the orchestrator.

        Raises:
            PermissionError: If no active consent exists for this elder.
        """
        if not await self.check(elder_id):
            raise PermissionError(
                f"No active consent for elder {elder_id}; refusing to process event. "
                f"The elder must grant consent before Guardian Angel can analyze calls."
            )

        logger.info("Consent verified for elder %s — processing event", elder_id)

        # Import here to avoid circular dependency
        from agents.orchestrator import analyze_call_event

        result = await analyze_call_event(call_event)

        # Log to audit trail
        await self.database.append_audit_log(
            elder_id=elder_id,
            event_type="call_analyzed",
            risk_decision=result,
            metadata={
                "caller_number": call_event.get("caller_number"),
                "claimed_identity": call_event.get("claimed_identity"),
                "had_transaction": call_event.get("has_transaction", False),
            },
        )

        return result
