"""Redis caching service for MOZG Analytics."""

import hashlib
import json
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal
from functools import wraps
from typing import Any, Callable, Optional, TypeVar, Union

import redis.asyncio as redis
from pydantic import BaseModel

from app.core.config import settings

# Type variable for generic return types
T = TypeVar("T")


class CacheEncoder(json.JSONEncoder):
    """Custom JSON encoder for cache serialization."""

    def default(self, obj):
        if isinstance(obj, Decimal):
            return {"__decimal__": str(obj)}
        elif isinstance(obj, date):
            return {"__date__": obj.isoformat()}
        elif isinstance(obj, datetime):
            return {"__datetime__": obj.isoformat()}
        elif isinstance(obj, uuid.UUID):
            return {"__uuid__": str(obj)}
        elif isinstance(obj, BaseModel):
            return {"__pydantic__": obj.model_dump()}
        return super().default(obj)


def cache_decoder(obj: dict) -> Any:
    """Custom JSON decoder for cache deserialization."""
    if "__decimal__" in obj:
        return Decimal(obj["__decimal__"])
    elif "__date__" in obj:
        return date.fromisoformat(obj["__date__"])
    elif "__datetime__" in obj:
        return datetime.fromisoformat(obj["__datetime__"])
    elif "__uuid__" in obj:
        return uuid.UUID(obj["__uuid__"])
    elif "__pydantic__" in obj:
        return obj["__pydantic__"]
    return obj


class CacheService:
    """Redis-based caching service for reports."""

    PREFIX = "mozg:cache:"
    DEFAULT_TTL = 300  # 5 minutes

    def __init__(self, redis_url: Optional[str] = None):
        self.redis_url = redis_url or settings.REDIS_URL
        self._redis: Optional[redis.Redis] = None

    async def get_redis(self) -> redis.Redis:
        """Get or create Redis connection."""
        if self._redis is None:
            self._redis = redis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
        return self._redis

    async def close(self):
        """Close Redis connection."""
        if self._redis:
            await self._redis.close()
            self._redis = None

    def _make_key(self, *args, **kwargs) -> str:
        """Generate cache key from arguments."""
        # Create a deterministic string from args and kwargs
        key_parts = []

        for arg in args:
            if isinstance(arg, (list, tuple)):
                key_parts.append(",".join(str(x) for x in sorted(arg)))
            elif isinstance(arg, uuid.UUID):
                key_parts.append(str(arg))
            else:
                key_parts.append(str(arg))

        for k, v in sorted(kwargs.items()):
            if isinstance(v, (list, tuple)):
                key_parts.append(f"{k}={','.join(str(x) for x in sorted(v))}")
            elif isinstance(v, uuid.UUID):
                key_parts.append(f"{k}={str(v)}")
            else:
                key_parts.append(f"{k}={v}")

        key_string = "|".join(key_parts)
        key_hash = hashlib.md5(key_string.encode()).hexdigest()[:16]
        return key_hash

    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        r = await self.get_redis()
        full_key = f"{self.PREFIX}{key}"
        value = await r.get(full_key)

        if value is None:
            return None

        try:
            return json.loads(value, object_hook=cache_decoder)
        except json.JSONDecodeError:
            return None

    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
    ):
        """Set value in cache with TTL."""
        r = await self.get_redis()
        full_key = f"{self.PREFIX}{key}"
        ttl = ttl or self.DEFAULT_TTL

        serialized = json.dumps(value, cls=CacheEncoder)
        await r.setex(full_key, ttl, serialized)

    async def delete(self, key: str):
        """Delete key from cache."""
        r = await self.get_redis()
        full_key = f"{self.PREFIX}{key}"
        await r.delete(full_key)

    async def delete_pattern(self, pattern: str):
        """Delete all keys matching pattern."""
        r = await self.get_redis()
        full_pattern = f"{self.PREFIX}{pattern}"

        cursor = 0
        while True:
            cursor, keys = await r.scan(cursor, match=full_pattern, count=100)
            if keys:
                await r.delete(*keys)
            if cursor == 0:
                break

    async def invalidate_venue(self, venue_id: uuid.UUID):
        """Invalidate all cache entries for a venue."""
        await self.delete_pattern(f"*{venue_id}*")

    async def invalidate_reports(self):
        """Invalidate all report caches."""
        await self.delete_pattern("report:*")


# Global cache instance
cache_service = CacheService()


def cached(
    key_prefix: str,
    ttl: Optional[int] = None,
    include_venue_ids: bool = True,
):
    """
    Decorator for caching async function results.

    Args:
        key_prefix: Prefix for cache key (e.g., "report:sales:summary")
        ttl: Time-to-live in seconds (default: 300)
        include_venue_ids: Whether to include venue_ids in cache key

    Usage:
        @cached("report:sales:summary", ttl=600)
        async def get_sales_summary(venue_ids, date_from, date_to):
            ...
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            # Build cache key
            key_parts = [key_prefix]

            # Extract venue_ids if present
            if include_venue_ids:
                venue_ids = kwargs.get("venue_ids") or (args[0] if args else None)
                if venue_ids:
                    if isinstance(venue_ids, list):
                        venue_key = ",".join(sorted(str(v) for v in venue_ids))
                    else:
                        venue_key = str(venue_ids)
                    key_parts.append(venue_key)

            # Add date range if present
            date_from = kwargs.get("date_from")
            date_to = kwargs.get("date_to")
            if date_from:
                key_parts.append(str(date_from))
            if date_to:
                key_parts.append(str(date_to))

            # Add other kwargs
            for k, v in sorted(kwargs.items()):
                if k not in ("venue_ids", "date_from", "date_to", "db"):
                    key_parts.append(f"{k}={v}")

            cache_key = ":".join(key_parts)

            # Try to get from cache
            cached_value = await cache_service.get(cache_key)
            if cached_value is not None:
                return cached_value

            # Execute function
            result = await func(*args, **kwargs)

            # Convert dataclasses to dicts for caching
            if hasattr(result, "__dataclass_fields__"):
                result_dict = {
                    k: getattr(result, k) for k in result.__dataclass_fields__
                }
                await cache_service.set(cache_key, result_dict, ttl)
            elif isinstance(result, list):
                # Handle list of dataclasses
                if result and hasattr(result[0], "__dataclass_fields__"):
                    result_list = [
                        {k: getattr(item, k) for k in item.__dataclass_fields__}
                        for item in result
                    ]
                    await cache_service.set(cache_key, result_list, ttl)
                else:
                    await cache_service.set(cache_key, result, ttl)
            else:
                await cache_service.set(cache_key, result, ttl)

            return result

        return wrapper

    return decorator


class ReportCacheKeys:
    """Standard cache key prefixes for reports."""

    SALES_SUMMARY = "report:sales:summary"
    SALES_DAILY = "report:sales:daily"
    SALES_HOURLY = "report:sales:hourly"
    SALES_BY_VENUE = "report:sales:by_venue"
    SALES_COMPARISON = "report:sales:comparison"

    MENU_ABC = "report:menu:abc"
    MENU_MARGIN = "report:menu:margin"
    MENU_GO_LIST = "report:menu:go_list"
    MENU_TOP_SELLERS = "report:menu:top_sellers"
    MENU_CATEGORIES = "report:menu:categories"


async def get_cache() -> CacheService:
    """Dependency for getting cache service."""
    return cache_service
