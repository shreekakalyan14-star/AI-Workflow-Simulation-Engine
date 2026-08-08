"""
DEV-ONLY endpoint.

This service never issues tokens in production — Module 1 (the parent
platform's auth service) does. This route exists purely so the frontend
(and anyone testing this microservice standalone, before Module 1
integration) can obtain a valid token. It is hard-disabled unless
ENVIRONMENT=development.
"""
from fastapi import APIRouter, HTTPException, status
from jose import jwt
from pydantic import BaseModel, Field

from app.core.config import settings

router = APIRouter(prefix="/api/dev", tags=["Dev — remove before production"])


class DevTokenRequest(BaseModel):
    student_id: str = Field(..., min_length=1, examples=["student_001"])
    role: str = Field(default="student")


class DevTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post("/token", response_model=DevTokenResponse)
def mint_dev_token(payload: DevTokenRequest):
    if settings.ENVIRONMENT != "development":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Not found",
        )

    token = jwt.encode(
        {"sub": payload.student_id, "student_id": payload.student_id, "role": payload.role},
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    return DevTokenResponse(access_token=token)
