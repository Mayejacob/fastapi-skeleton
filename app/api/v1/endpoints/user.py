from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import DBDependency
from app.core.responses import send_success, send_error
from app.core.security import create_access_token, get_current_user, get_password_hash
from app.db.models.user import User
from app.db.schemas.user import UserCreate, UserResponse

router = APIRouter(prefix="/users", tags=["users"])


@router.post("/", response_model=UserResponse)
async def create_user(user: UserCreate, db: DBDependency):
    async with db.begin():
        existing_user = await db.execute(
            User.__table__.select().where(User.username == user.username)
        )
        if existing_user.first():
            raise HTTPException(
                status_code=400,
                detail=send_error("Username already exists").model_dump(),
            )
        hashed_password = get_password_hash(user.password)
        db_user = User(
            username=user.username, email=user.email, hashed_password=hashed_password
        )
        db.add(db_user)
        await db.commit()
        await db.refresh(db_user)
    return send_success(data=UserResponse.from_orm(db_user)).model_dump()


@router.get("/me", response_model=UserResponse)
async def read_users_me(current_user: Annotated[dict, Depends(get_current_user)]):
    return send_success(data=UserResponse.from_orm(current_user)).model_dump()
