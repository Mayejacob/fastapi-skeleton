from typing import Any, Optional

import redis.asyncio as aioredis

from app.core.config import settings


class Cache:
    def __init__(self):
        self._redis = None
        self._inmemory = {}
        self.cache_type = settings.CACHE_TYPE.lower()

    async def init_redis(self):
        if self.cache_type == "redis" and settings.REDIS_URL:
            self._redis = aioredis.from_url(settings.REDIS_URL)

    async def get(self, key: str) -> Optional[Any]:
        if self.cache_type == "redis" and self._redis:
            return await self._redis.get(key)
        return self._inmemory.get(key)

    async def set(self, key: str, value: Any, expire: int = 3600):
        if self.cache_type == "redis" and self._redis:
            await self._redis.set(key, value, ex=expire)
        else:
            self._inmemory[key] = value

    async def close(self):
        if self._redis:
            await self._redis.close()


cache = Cache()
