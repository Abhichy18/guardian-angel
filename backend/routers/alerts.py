"""
Guardian Angel — Alerts Feed Router

Exposes feeds of scam alerts for both elder and family dashboards.
Ensures authorization checks:
- Elders can only view their own alerts.
- Family members can only view alerts for elders who have actively granted them consent.
"""

import logging
from fastapi import APIRouter, HTTPException, Depends, status
from typing import List

from database.db import db
from database.models import AlertResponse, AlertDetail, UserRole
from backend.routers.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/alerts", tags=["alerts"])

@router.get("/elder/{elder_id}", response_model=List[AlertResponse])
async def get_elder_alerts(elder_id: str, current_user: dict = Depends(get_current_user)):
    """Retrieve all alerts for a specific elder. Visible on the elder's own dashboard."""
    if current_user["role"] != UserRole.ELDER or current_user["id"] != elder_id:
        raise HTTPException(
            status_code=403,
            detail="Unauthorized: Elders can only view their own alert feed."
        )
        
    await db.connect()
    try:
        alerts = await db.get_alerts_for_elder(elder_id)
        # Map DB row keys to Pydantic models
        return [AlertResponse(**a) for a in alerts]
    finally:
        await db.close()

@router.get("/family/{family_id}", response_model=List[AlertResponse])
async def get_family_alerts(family_id: str, current_user: dict = Depends(get_current_user)):
    """Retrieve alerts for all elders who have authorized this family member."""
    if current_user["role"] != UserRole.FAMILY or current_user["id"] != family_id:
        raise HTTPException(
            status_code=403,
            detail="Unauthorized: Family members can only view alert feeds authorized for them."
        )
        
    await db.connect()
    try:
        alerts = await db.get_alerts_for_family(family_id)
        return [AlertResponse(**a) for a in alerts]
    finally:
        await db.close()

@router.get("/{alert_id}", response_model=AlertDetail)
async def get_alert_detail(alert_id: str, current_user: dict = Depends(get_current_user)):
    """Retrieve detailed analysis for a single alert. Subject to authorization check."""
    await db.connect()
    try:
        alert = await db.get_alert_by_id(alert_id)
        if not alert:
            raise HTTPException(
                status_code=404,
                detail="Alert not found."
            )
            
        # Authorization check
        if current_user["role"] == UserRole.ELDER:
            # Elder must own this alert
            if current_user["id"] != alert["elder_id"]:
                raise HTTPException(
                    status_code=403,
                    detail="Unauthorized: You do not have access to this alert."
                )
        elif current_user["role"] == UserRole.FAMILY:
            # Family member must be authorized by the elder who owns this alert
            consent = await db.get_consent(alert["elder_id"])
            if not consent or current_user["id"] not in consent["authorized_family_ids"]:
                raise HTTPException(
                    status_code=403,
                    detail="Unauthorized: You do not have access to this elder's alerts."
                )
                
        return AlertDetail(**alert)
    finally:
        await db.close()
