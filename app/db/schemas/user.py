from pydantic import BaseModel, EmailStr
import uuid


class UserBase(BaseModel):
    username: str
    email: EmailStr


class UserCreate(UserBase):
    password: str


class UserResponse(UserBase):
    id: uuid.UUID

    class Config:
        from_attributes = True
