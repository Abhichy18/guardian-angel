"""
Guardian Angel — Authentication Router

Handles registration, login, and session validation for elders and family members.
Uses a simplified PIN-based authentication system suitable for elder accessibility,
backed by secure bcrypt hashing and JWT session tokens.
"""

from datetime import datetime, timedelta, timezone
import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from passlib.context import CryptContext
from pydantic import BaseModel

from database.db import db
from database.models import UserCreate, UserLogin, UserResponse, UserRole

logger = logging.getLogger(__name__)

# Security configuration
SECRET_KEY = "super_secret_guardian_angel_key_change_me_in_production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 # 24 hours for ease of use

import bcrypt

security = HTTPBearer()

router = APIRouter(prefix="/api/auth", tags=["authentication"])

class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    user: UserResponse

def hash_pin(pin: str) -> str:
    hashed = bcrypt.hashpw(pin.encode('utf-8'), bcrypt.gensalt())
    return hashed.decode('utf-8')

def verify_pin(plain_pin: str, hashed_pin: str) -> bool:
    try:
        return bcrypt.checkpw(plain_pin.encode('utf-8'), hashed_pin.encode('utf-8'))
    except Exception:
        return False

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """Dependency to retrieve the logged-in user from the JWT token."""
    token = credentials.credentials
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
        
    await db.connect()
    user = await db.get_user_by_id(user_id)
    await db.close()
    
    if user is None:
        raise credentials_exception
    return user

@router.post("/register", response_model=TokenResponse)
async def register(user_in: UserCreate):
    """Register a new user (Elder or Family Member)."""
    await db.connect()
    try:
        # Check if user already exists
        existing = await db.get_user_by_name(user_in.name)
        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"User with name '{user_in.name}' is already registered."
            )
            
        # Hash the PIN and create the user
        hashed = hash_pin(user_in.pin)
        user = await db.create_user(name=user_in.name, role=user_in.role.value, pin_hash=hashed)
        
        # If the user is an elder, automatically initialize a consent record for them
        if user_in.role == UserRole.ELDER:
            await db.grant_consent(elder_id=user["id"], authorized_family_ids=[])
            
        # Generate JWT access token
        access_token = create_access_token(
            data={"sub": user["id"], "role": user["role"]},
            expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        )
        
        user_res = UserResponse(
            id=user["id"],
            name=user["name"],
            role=UserRole(user["role"]),
            created_at=user["created_at"]
        )
        
        return TokenResponse(
            access_token=access_token,
            token_type="bearer",
            user=user_res
        )
    finally:
        await db.close()

@router.post("/login", response_model=TokenResponse)
async def login(login_in: UserLogin):
    """Authenticate a user and return a JWT access token."""
    await db.connect()
    try:
        user = await db.get_user_by_name(login_in.name)
        if not user or not verify_pin(login_in.pin, user["pin_hash"]):
            raise HTTPException(
                status_code=401,
                detail="Invalid username or PIN."
            )
            
        access_token = create_access_token(
            data={"sub": user["id"], "role": user["role"]},
            expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        )
        
        user_res = UserResponse(
            id=user["id"],
            name=user["name"],
            role=UserRole(user["role"]),
            created_at=user["created_at"]
        )
        
        return TokenResponse(
            access_token=access_token,
            token_type="bearer",
            user=user_res
        )
    finally:
        await db.close()

@router.get("/me", response_model=UserResponse)
async def get_me(current_user: dict = Depends(get_current_user)):
    """Return the profile of the currently logged-in user."""
    return UserResponse(
        id=current_user["id"],
        name=current_user["name"],
        role=UserRole(current_user["role"]),
        created_at=current_user["created_at"]
    )
