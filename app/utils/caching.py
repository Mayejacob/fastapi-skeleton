from typing import Any, Optional
import json
import redis.asyncio as aioredis
from datetime import datetime, timedelta, timezone

from app.core.config import settings
from app.db.models.cache import CacheEntry
from app.core.dependencies import DBDependency  # Reuse DB dep


class Cache:
    def __init__(self):
        self._redis = None
        self._inmemory = {}
        self.cache_type = settings.CACHE_TYPE.lower()

    async def init_redis(self):
        if self.cache_type == "redis" and settings.REDIS_URL:
            self._redis = aioredis.from_url(settings.REDIS_URL)

    async def get(self, key: str, db: Optional[DBDependency] = None) -> Optional[Any]:
        if self.cache_type == "redis" and self._redis:
            value = await self._redis.get(key)
            if value:
                return json.loads(value) if value else None
        elif self.cache_type == "database" and db:
            entry = await db.execute(
                CacheEntry.__table__.select().where(CacheEntry.key == key)
            )
            entry = entry.first()
            if entry and (
                not entry.expires_at or entry.expires_at > datetime.now(timezone.utc)
            ):
                return json.loads(entry.value)
            elif entry:  # Expired
                await db.delete(entry)
                await db.commit()
        else:  # inmemory
            return self._inmemory.get(key)
        return None

    async def set(
        self,
        key: str,
        value: Any,
        expire: int = 3600,
        db: Optional[DBDependency] = None,
    ):
        val_str = json.dumps(value)
        if self.cache_type == "redis" and self._redis:
            await self._redis.set(key, val_str, ex=expire)
        elif self.cache_type == "database" and db:
            async with db.begin():
                # Delete existing
                await db.execute(
                    CacheEntry.__table__.delete().where(CacheEntry.key == key)
                )
                # Insert new
                expires_at = (
                    datetime.now(timezone.utc) + timedelta(seconds=expire)
                    if expire
                    else None
                )
                new_entry = CacheEntry(key=key, value=val_str, expires_at=expires_at)
                db.add(new_entry)
                await db.commit()
        else:  # inmemory (no expire support, or use threading.Timer if needed)
            self._inmemory[key] = value

    async def close(self):
        if self._redis:
            await self._redis.close()


cache = Cache()
