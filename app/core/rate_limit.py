from redis.exceptions import RedisError

from app.core.config import settings
from app.core.redis_client import get_redis


async def is_rate_limited(key: str, limit: int, window_seconds: int) -> bool:
    namespaced = f"{settings.redis_key_prefix}:ratelimit:{key}"
    try:
        redis = get_redis()
        current = await redis.incr(namespaced)
        if current == 1:
            await redis.expire(namespaced, window_seconds)
        return current > limit
    except (RedisError, RuntimeError):
        if settings.auth_fail_closed:
            raise RuntimeError("Rate limit backend unavailable")
        return False
