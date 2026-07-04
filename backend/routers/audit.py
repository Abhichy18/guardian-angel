"""
Guardian Angel — Audit Trail Router

Exposes a read-only audit log feed for elders to inspect all actions,
consent updates, and risk decisions taken on their behalf.
Enforces that only the elder themselves can read their immutable audit log.
"""

import logging
from fastapi import APIRouter, HTTPException, Depends, status
from typing import List

from database.db import db
from database.models import AuditLogEntry, UserRole
from backend.routers.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/audit", tags=["audit"])

@router.get("/{elder_id}", response_model=List[AuditLogEntry])
async def get_elder_audit_log(elder_id: str, current_user: dict = Depends(get_current_user)):
    """
    Retrieve the append-only audit trail for an elder.
    Only the elder themselves is allowed to view their raw audit trail for transparency.
    """
    if current_user["role"] != UserRole.ELDER or current_user["id"] != elder_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Unauthorized: Only the elder can view their raw audit log trail."
        )
        
    await db.connect()
    try:
        logs = await db.get_audit_log(elder_id)
        
        response = []
        for log in logs:
            response.append(AuditLogEntry(
                id=log["id"],
                elder_id=log["elder_id"],
                event_type=log["event_type"],
                risk_decision=log.get("risk_decision"),
                metadata=log.get("metadata"),
                timestamp=log["timestamp"]
            ))
        return response
    finally:
        await db.close()
