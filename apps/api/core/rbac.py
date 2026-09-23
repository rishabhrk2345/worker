"""
apps/api/core/rbac.py

Tenant context and Role-Based Access Control (RBAC) middleware for FastAPI.
Enforces that every authenticated request is bound to an organization_id and
has sufficient permissions for the requested operation.
"""

from typing import List, Optional
from dataclasses import dataclass
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from .config import settings
from .security import decode_access_token

security_scheme = HTTPBearer(auto_error=False)

@dataclass
class TenantContext:
    user_id: str
    organization_id: str
    role: str
    permissions: List[str]

    def has_permission(self, permission: str) -> bool:
        if self.role in ("owner", "admin"):
            return True
        return permission in self.permissions

async def get_tenant_context(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security_scheme)
) -> TenantContext:
    """
    Extracts TenantContext from Bearer JWT.
    In development / simulation mode, if no header is provided, it falls back
    to the default seed organization context to streamline initial dev.
    """
    if not credentials:
        if settings.APP_ENV in ("development", "simulation"):
            return TenantContext(
                user_id="00000000-0000-0000-0000-000000000099",
                organization_id=settings.DEFAULT_ORG_ID,
                role="owner",
                permissions=["*"]
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_access_token(credentials.credentials)
        return TenantContext(
            user_id=payload["sub"],
            organization_id=payload["org_id"],
            role=payload.get("role", "member"),
            permissions=payload.get("permissions", [])
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

def require_permission(permission: str):
    """
    FastAPI dependency factory enforcing a specific permission.
    Example:
        @router.post("/products")
        async def create_product(ctx: TenantContext = Depends(require_permission("product:write"))):
            ...
    """
    async def dependency(ctx: TenantContext = Depends(get_tenant_context)) -> TenantContext:
        if not ctx.has_permission(permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied. Required: '{permission}'"
            )
        return ctx
    return dependency
