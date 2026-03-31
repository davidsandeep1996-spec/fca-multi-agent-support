"""
Handles Redis connection and global semantic caching for high-frequency queries.
"""

import logging
from typing import Optional
import redis.asyncio as redis
from app.config import settings


class CacheService:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        # Fallback to local default if not set in environment variables
        redis_url = getattr(settings, "redis_url", "redis://localhost:6379/1")
        self.redis_client = redis.from_url(redis_url, decode_responses=True)

    async def get_cached_response(self, query: str) -> Optional[str]:
        """Fetch a cached response using a normalized version of the user's query."""
        try:
            cache_key = self._generate_key(query)
            cached_data = await self.redis_client.get(cache_key)

            if cached_data:
                self.logger.info(f"⚡ REDIS CACHE HIT: '{query}'")
                return cached_data
            return None
        except Exception as e:
            self.logger.error(f"Redis GET Error: {e}")
            return None

    async def set_cached_response(
        self, query: str, response: str, ttl_seconds: int = 3600
    ):
        """Save a response to Redis with a Time-To-Live (TTL)."""
        try:
            cache_key = self._generate_key(query)
            # Store in Redis and expire after TTL
            await self.redis_client.setex(cache_key, ttl_seconds, response)
            self.logger.info(f"💾 SAVED TO REDIS: '{query}' (TTL: {ttl_seconds}s)")
        except Exception as e:
            self.logger.error(f"Redis SET Error: {e}")

    def _generate_key(self, query: str) -> str:
        """Normalize the query to ensure minor typos/casing don't miss the cache."""
        # Lowercase, strip whitespace, and remove punctuation/special characters
        normalized = "".join(
            c for c in query.lower() if c.isalnum() or c.isspace()
        ).strip()
        # Collapse multiple spaces into one
        normalized = " ".join(normalized.split())
        return f"faq_cache:{normalized}"
