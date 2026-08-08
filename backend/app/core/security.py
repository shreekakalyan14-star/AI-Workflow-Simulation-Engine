"""
JWT validation.

This microservice never issues tokens. It only validates tokens that were
issued elsewhere (the parent AI Internship Simulator platform / Module 1
auth service), using a shared signing secret (JWT_SECRET_KEY).
"""
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel

from app.core.config import settings

bearer_scheme = HTTPBearer(auto_error=False)


class CurrentUser(BaseModel):
    student_id: str
    role: Optional[str] = None
    raw_claims: dict


def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        return payload
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired token: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> CurrentUser:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_token(credentials.credentials)
    student_id = payload.get("sub") or payload.get("student_id")
    if not student_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing subject/student_id claim",
        )

    return CurrentUser(
        student_id=str(student_id),
        role=payload.get("role"),
        raw_claims=payload,
    )


def require_role(*allowed_roles: str):
    """Dependency factory for simple role-based access control."""

    def _checker(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if allowed_roles and user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{user.role}' is not permitted to access this resource",
            )
        return user

    return _checker
