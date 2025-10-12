from datetime import datetime, timedelta, timezone
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import InvalidTokenError

# from passlib.context import CryptContext
import bcrypt
from pydantic import BaseModel
import hashlib  # Added for SHA-256
from random import randint

from itsdangerous import URLSafeTimedSerializer

from app.core.config import settings

# pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: str | None = None


def get_password_hash(password: str) -> str:
    password_bytes = password.encode("utf-8")
    # Optional: protect bcrypt 72-byte limit
    if len(password_bytes) > 72:
        password = hashlib.sha256(password_bytes).hexdigest()
        password_bytes = password.encode("utf-8")

    hashed = bcrypt.hashpw(password_bytes, bcrypt.gensalt())
    return hashed.decode("utf-8")  # ✅ store as string


def verify_password(plain_password: str, hashed_password: str) -> bool:
    plain_bytes = plain_password.encode("utf-8")
    if len(plain_bytes) > 72:
        plain_password = hashlib.sha256(plain_bytes).hexdigest()
        plain_bytes = plain_password.encode("utf-8")

    return bcrypt.checkpw(plain_bytes, hashed_password.encode("utf-8"))


def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(
        to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM
    )
    return encoded_jwt


async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        email: str = payload.get("sub")  # <-- 'sub' holds the email
        if email is None:
            raise credentials_exception
        token_data = TokenData(username=email)  # or rename TokenData to TokenEmail
    except InvalidTokenError:
        raise credentials_exception

    from app.db.models.user import User
    from app.db.session import SessionLocal

    async with SessionLocal() as db:
        user = await db.execute(
            User.__table__.select().where(User.email == token_data.username)
        )
        user = user.first()
        if user is None:
            raise credentials_exception

    return user


# For email/reset tokens (signed, timed)
def create_verification_token(email: str, expires_in_hours: int = 24) -> str:
    s = URLSafeTimedSerializer(settings.SECRET_KEY)
    return s.dumps(email, salt="email-verify")


def verify_verification_token(token: str, max_age_hours: int = 24) -> str:
    s = URLSafeTimedSerializer(settings.SECRET_KEY)
    try:
        email = s.loads(
            token, salt="email-verify", max_age_seconds=max_age_hours * 3600
        )
        return email
    except:
        raise HTTPException(status_code=400, detail="Invalid or expired token")


def create_reset_token(email: str, expires_in_hours: int = 1) -> str:
    s = URLSafeTimedSerializer(settings.SECRET_KEY)
    return s.dumps(email, salt="password-reset")


def verify_reset_token(token: str, max_age_hours: int = 1) -> str:
    s = URLSafeTimedSerializer(settings.SECRET_KEY)
    try:
        email = s.loads(
            token, salt="password-reset", max_age_seconds=max_age_hours * 3600
        )
        return email
    except:
        raise HTTPException(status_code=400, detail="Invalid or expired token")


# account verification code


def generate_verification_code() -> str:
    return f"{randint(100000, 999999)}"  # 6-digit code


def hash_verification_code(code: str) -> str:
    return bcrypt.hashpw(code.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_verification_code(stored_hash: str, provided_code: str) -> bool:
    if not stored_hash or not provided_code:
        return False
    return bcrypt.checkpw(provided_code.encode("utf-8"), stored_hash.encode("utf-8"))
