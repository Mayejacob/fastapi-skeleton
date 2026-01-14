import select
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
            # use ORM select to get a real cacheEntryu instanjce
            result = await db.execute(
                select(CacheEntry).where(CacheEntry.key == key)
            )
            entry: Optional[CacheEntry] = result.scalars().first()

            if entry:
                # check if expired
                if entry.expires_at and entry.expires_at <= datetime.now(timezone.utc):
                    await db.delete(entry)
                    await db.commit()
                    return None
                else:
                    return json.loads(entry.value)
            return None
        
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
            # Delete existing
            await db.execute(CacheEntry.__table__.delete().where(CacheEntry.key == key))
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

    async def delete(self, key: str, db: Optional[DBDependency] = None):
        if self.cache_type == "redis" and self._redis:
            await self._redis.delete(key)

        elif self.cache_type == "database" and db:
            await db.execute(
                CacheEntry.__table__.delete().where(CacheEntry.key == key)
            )
            await db.commit()
        else:  # inmemory
            self._inmemory.pop(key, None)
            
    async def close(self):
        if self._redis:
            await self._redis.close()


cache = Cache()
