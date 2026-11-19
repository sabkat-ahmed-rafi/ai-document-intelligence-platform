import redis.asyncio as aioredis
from redis.asyncio import Redis
from core.config import settings

_async_redis_client: Redis | None = None


def get_async_redis_client() -> Redis:
    """Returns a singleton asynchronous Redis client connected to settings.REDIS_URL."""
    global _async_redis_client
    if _async_redis_client is None:
        _async_redis_client = aioredis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            health_check_interval=30,
        )
    return _async_redis_client


async def close_async_redis_client() -> None:
    """Closes the active singleton Redis client cleanly on shutdown."""
    global _async_redis_client
    if _async_redis_client is not None:
        await _async_redis_client.aclose()
        _async_redis_client = None
