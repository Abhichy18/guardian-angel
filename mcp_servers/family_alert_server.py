"""
Guardian Angel — Family Alert / Notification MCP Server

Exposes a tool to trigger alerts for family members when high-risk events are detected.
Note: Intentionally limits information sent to family to reasons and summary. NEVER sends raw transcripts.
Exposes tool: `send_family_alert`
"""

import os
from typing import List, Optional
from mcp.server.fastmcp import FastMCP
from database.db import db

mcp = FastMCP("family-alert-server")

@mcp.tool()
async def send_family_alert(
    elder_id: str,
    risk_score: int,
    tier: str,
    reasons: List[str],
    summary: str,
    action_taken: str,
    caller_number: Optional[str] = None,
    caller_verification_score: Optional[int] = None,
    scam_pattern_score: Optional[int] = None,
    urgency_pressure_score: Optional[int] = None,
    matched_phrases: Optional[List[str]] = None,
    transaction_flagged: bool = False
) -> dict:
    """
    Trigger a notification and record an alert in the database for the authorized family.
    Intentionally logs summary information and reasons only. Never logs or sends the raw call transcript.
    """
    # Connect to the SQLite database
    # In stdio mode, this runs as a subprocess. We connect to the db, perform the insert, and commit.
    try:
        await db.connect()
        
        # Verify the elder has active consent first
        consent = await db.get_consent(elder_id)
        if not consent or not consent.get("active") or consent.get("revoked"):
            return {
                "success": False,
                "reason": f"Alert block: No active consent record found for elder {elder_id}."
            }
            
        # Create alert entry in database
        alert_record = await db.create_alert(
            elder_id=elder_id,
            risk_score=risk_score,
            tier=tier,
            reasons=reasons,
            action_taken=action_taken,
            summary_text=summary,
            caller_number=caller_number,
            caller_verification_score=caller_verification_score,
            scam_pattern_score=scam_pattern_score,
            urgency_pressure_score=urgency_pressure_score,
            matched_phrases=matched_phrases,
            transaction_flagged=transaction_flagged
        )
        
        # Simulate triggering push notifications/SMS to all authorized family members
        family_ids = consent.get("authorized_family_ids", [])
        
        # Build the limited payload (strictly excludes raw transcript)
        family_notification_payload = {
            "alert_id": alert_record["id"],
            "elder_id": elder_id,
            "tier": tier,
            "reasons": reasons,
            "summary_text": summary,
            "action_taken": action_taken,
            "timestamp": alert_record["created_at"]
        }
        
        # In a real application, we would call an SMS/Push gateway here (e.g. Twilio, FCM)
        # For now, we mock the dispatch
        dispatched_to = []
        for family_id in family_ids:
            # Mock sending notification
            dispatched_to.append(family_id)
            
        await db.close()
        
        return {
            "success": True,
            "alert_id": alert_record["id"],
            "notified_family_count": len(dispatched_to),
            "dispatched_to": dispatched_to,
            "payload_sent": family_notification_payload,
            "message": f"High risk alert logged. {len(dispatched_to)} family members notified."
        }
    except Exception as e:
        # Guarantee closure
        try:
            await db.close()
        except Exception:
            pass
        return {
            "success": False,
            "reason": f"Database insertion failed: {str(e)}"
        }

if __name__ == "__main__":
    mcp.run()
