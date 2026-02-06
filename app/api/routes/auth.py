"""
Authentication Router
Handles login and token generation.
"""
from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.database import get_db
from app.config import settings
from app.services.security_service import SecurityService
from app.models.customer import Customer

router = APIRouter(prefix="/auth", tags=["Authentication"])
security_service = SecurityService()

# Schema for the Token response
class Token(BaseModel):
    access_token: str
    token_type: str

@router.post("/login", response_model=Token)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """
    OAuth2 compatible token login.

    - **username**: Customer Email
    - **password**: Plain text password
    """
    # 1. Fetch User by Email
    # Note: OAuth2 form uses 'username' field, we map it to email
    query = select(Customer).where(Customer.email == form_data.username)
    result = await db.execute(query)
    user = result.scalar_one_or_none()

    # 2. Validate Credentials
    if not user:
        # Generic error message to prevent user enumeration
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Verify password hash
    if not user.hashed_password or not security_service.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 3. Generate Token with Scopes
    access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)

    # We embed the customer_id, database ID, and roles into the token
    access_token = security_service.create_access_token(
        data={
            "sub": str(user.customer_id), # Subject is the business ID
            "id": user.id,                # Primary Key
            "role": user.role,            # RBAC Role
            "scopes": user.scopes         # Permissions
        },
        expires_delta=access_token_expires
    )

    return {"access_token": access_token, "token_type": "bearer"}
