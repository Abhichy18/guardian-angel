"""
Guardian Angel — Consent Management Router

Enables the elder-led consent flow and three-party handshake onboarding.
Only the elder can grant consent, view authorization status, revoke consent (one-tap,
no dark patterns), and generate invite codes.
Only the family member can redeem an invite code (which links them to the elder).
"""

import logging
from fastapi import APIRouter, HTTPException, Depends, status
from typing import List

from database.db import db
from database.models import ConsentGrant, ConsentStatus, InviteCodeResponse, InviteRedeem, UserRole
from backend.routers.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/consent", tags=["consent"])

@router.get("/status", response_model=ConsentStatus)
async def get_consent_status(current_user: dict = Depends(get_current_user)):
    """Retrieve the current consent status for the logged-in elder."""
    if current_user["role"] != UserRole.ELDER:
        raise HTTPException(
            status_code=403,
            detail="Only elders can view their consent status."
        )
        
    await db.connect()
    try:
        consent = await db.get_consent(current_user["id"])
        if not consent:
            # Create a default active consent record if none exists (should be created on registration)
            consent = await db.grant_consent(current_user["id"], [])
            
        return ConsentStatus(
            elder_id=consent["elder_id"],
            active=consent["active"],
            revoked=consent["revoked"],
            authorized_family_ids=consent["authorized_family_ids"],
            created_at=consent.get("created_at"),
            updated_at=consent.get("updated_at")
        )
    finally:
        await db.close()

@router.post("/grant", response_model=ConsentStatus)
async def grant_consent(grant: ConsentGrant, current_user: dict = Depends(get_current_user)):
    """Elder grants consent and specifies authorized family members."""
    if current_user["role"] != UserRole.ELDER:
        raise HTTPException(
            status_code=403,
            detail="Only the elder can grant consent."
        )
        
    await db.connect()
    try:
        # Verify that all family IDs exist and are actually family members
        for family_id in grant.authorized_family_ids:
            user = await db.get_user_by_id(family_id)
            if not user or user["role"] != UserRole.FAMILY:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid family member ID: {family_id}"
                )
                
        consent = await db.grant_consent(
            elder_id=current_user["id"],
            authorized_family_ids=grant.authorized_family_ids
        )
        
        return ConsentStatus(
            elder_id=consent["elder_id"],
            active=consent["active"],
            revoked=consent["revoked"],
            authorized_family_ids=consent["authorized_family_ids"],
            updated_at=consent["updated_at"]
        )
    finally:
        await db.close()

@router.post("/revoke", response_model=ConsentStatus)
async def revoke_consent(current_user: dict = Depends(get_current_user)):
    """One-tap consent revocation. No dark patterns, no confirmations."""
    if current_user["role"] != UserRole.ELDER:
        raise HTTPException(
            status_code=403,
            detail="Only the elder can revoke consent."
        )
        
    await db.connect()
    try:
        await db.revoke_consent(current_user["id"])
        consent = await db.get_consent(current_user["id"])
        
        return ConsentStatus(
            elder_id=consent["elder_id"],
            active=consent["active"],
            revoked=consent["revoked"],
            authorized_family_ids=consent["authorized_family_ids"],
            created_at=consent.get("created_at"),
            updated_at=consent.get("updated_at")
        )
    finally:
        await db.close()

@router.post("/generate-invite", response_model=InviteCodeResponse)
async def generate_invite(current_user: dict = Depends(get_current_user)):
    """Elder generates an invite code to share with a family member."""
    if current_user["role"] != UserRole.ELDER:
        raise HTTPException(
            status_code=403,
            detail="Only elders can generate family invite codes."
        )
        
    await db.connect()
    try:
        invite = await db.create_invite_code(current_user["id"])
        return InviteCodeResponse(
            code=invite["code"],
            expires_at=invite["expires_at"]
        )
    finally:
        await db.close()

@router.post("/redeem-invite")
async def redeem_invite(redeem: InviteRedeem, current_user: dict = Depends(get_current_user)):
    """Family member redeems an invite code to get authorized access to an elder's alerts."""
    if current_user["role"] != UserRole.FAMILY:
        raise HTTPException(
            status_code=403,
            detail="Only family members can redeem invite codes."
        )
        
    await db.connect()
    try:
        elder_id = await db.redeem_invite_code(
            code=redeem.code,
            family_id=current_user["id"]
        )
        if not elder_id:
            raise HTTPException(
                status_code=400,
                detail="Invalid, used, or expired invite code."
            )
            
        elder = await db.get_user_by_id(elder_id)
        
        return {
            "success": True,
            "message": f"Successfully linked to elder '{elder['name']}'. You will now receive high-risk alerts.",
            "elder_id": elder_id,
            "elder_name": elder["name"]
        }
    finally:
        await db.close()
