from typing import Annotated, AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import SessionLocal

import logging

logger = logging.getLogger(__name__)
# async def get_db() -> AsyncGenerator[AsyncSession, None]:
#     async with SessionLocal() as session:
#         yield session


# DBDependency = Annotated[AsyncSession, Depends(get_db)]


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()  # ✅ Commit when all goes well
        except Exception as e:
            await session.rollback()  # ✅ Rollback on any error
            logger.exception(f"Database transaction rolled back: {e}")
            raise
        finally:
            await session.close()  # ✅ Ensure session is closed


DBDependency = Annotated[AsyncSession, Depends(get_db)]
