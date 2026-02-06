"""
API Dependencies

Reusable dependencies for dependency injection (Authentication, RBAC, Database).
"""
from typing import Generator, Annotated
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, SecurityScopes
from jose import JWTError, jwt
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.config import settings
from app.models.customer import Customer
from app.services.customer import CustomerService
from app.services.security_service import SecurityService

# Define the Token Url (relative path)
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/v1/auth/login",
    scopes={
        "read:accounts": "Read account balances",
        "write:transfer": "Execute transfers",
        "admin": "Admin privileges",
    }
)

async def get_current_user(
    security_scopes: SecurityScopes,
    token: Annotated[str, Depends(oauth2_scheme)],
    db: AsyncSession = Depends(get_db),
) -> Customer:
    """
    Validate Token & Scopes.
    Returns the user object if valid.
    """
    if security_scopes.scopes:
        authenticate_value = f'Bearer scope="{security_scopes.scope_str}"'
    else:
        authenticate_value = "Bearer"

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": authenticate_value},
    )

    try:
        # 1. Decode Token
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.jwt_algorithm]
        )
        customer_id: str = payload.get("sub")
        token_scopes = payload.get("scopes", "").split()

        if customer_id is None:
            raise credentials_exception

    except (JWTError, ValidationError):
        raise credentials_exception

    # 2. Check Scopes (RBAC)
    # If the endpoint requires scopes, check if the token has them
    for scope in security_scopes.scopes:
        if scope not in token_scopes:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not enough permissions",
                headers={"WWW-Authenticate": authenticate_value},
            )

    # 3. Get User from DB
    async with CustomerService(db) as service:
        user = await service.repo.get_by_customer_id(customer_id)
        if user is None:
            raise credentials_exception

    return user

async def get_current_active_user(
    current_user: Annotated[Customer, Depends(get_current_user)]
) -> Customer:
    """Ensure user is active."""
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user
