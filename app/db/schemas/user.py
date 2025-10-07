from pydantic import BaseModel, EmailStr, ConfigDict, Field as PydanticField
from uuid import UUID
from datetime import datetime
from typing import Optional


class UserBase(BaseModel):
    username: str
    email: EmailStr


class UserCreate(UserBase):
    password: str = PydanticField(..., min_length=8, max_length=72)


class UserResponse(UserBase):
    id: UUID
    is_active: bool
    email_verified_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# New: Login
class LoginRequest(BaseModel):
    username: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


# New: Verify/Reset
class VerifyRequest(BaseModel):
    token: str


class ResetRequest(BaseModel):
    token: str
    new_password: str = PydanticField(..., min_length=8, max_length=72)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class PasswordResetResponse(BaseModel):
    message: str
