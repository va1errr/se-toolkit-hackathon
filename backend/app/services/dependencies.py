"""FastAPI dependencies for authentication and authorization.

- `get_current_user` — extracts JWT from request, returns the User object
- `require_role` — factory that creates a role-checking dependency
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.database import get_session
from app.models.models import User
from app.services.auth import decode_access_token

security = HTTPBearer(auto_error=False)  # Don't auto-error — allow missing token


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    session: AsyncSession = Depends(get_session),
) -> User | None:
    """Extract and validate JWT, return the current user or None if not authenticated."""
    if credentials is None or credentials.credentials is None:
        return None  # Not authenticated — that's fine for public endpoints

    payload = decode_access_token(credentials.credentials)
    if payload is None:
        return None

    user_id_str = payload.get("sub")
    if user_id_str is None:
        return None

    result = await session.execute(select(User).where(User.id == user_id_str))
    return result.scalar_one_or_none()


async def get_required_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    session: AsyncSession = Depends(get_session),
) -> User:
    """Like get_current_user but raises 401 if not authenticated."""
    user = await get_current_user(credentials, session)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def require_role(minimum_role: str):
    """Factory that creates a role-checking dependency.

    Role hierarchy: student(0) < ta(1) < admin(2)
    A TA can do everything a student can, etc.

    Usage:
        @router.post("/admin-only", dependencies=[Depends(require_role("admin"))])
    """
    role_hierarchy = {"student": 0, "ta": 1, "admin": 2}
    minimum_level = role_hierarchy.get(minimum_role, 0)

    async def role_checker(user: User = Depends(get_required_user)) -> User:
        if role_hierarchy.get(user.role, 0) < minimum_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires '{minimum_role}' role or higher",
            )
        return user

    return role_checker
