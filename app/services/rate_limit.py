from __future__ import annotations

from dataclasses import dataclass

from redis.exceptions import RedisError

from app.core.config import settings
from app.core.redis_client import get_redis


SUPPORT_REPLY_RATE_LIMIT_LUA = """
local short_key = KEYS[1]
local long_key = KEYS[2]

local short_limit = tonumber(ARGV[1])
local short_window = tonumber(ARGV[2])
local long_limit = tonumber(ARGV[3])
local long_window = tonumber(ARGV[4])

local short_count = tonumber(redis.call("GET", short_key) or "0")
local long_count = tonumber(redis.call("GET", long_key) or "0")

local short_ttl = redis.call("TTL", short_key)
if short_count > 0 and short_ttl < 0 then
    redis.call("EXPIRE", short_key, short_window)
    short_ttl = short_window
end

local long_ttl = redis.call("TTL", long_key)
if long_count > 0 and long_ttl < 0 then
    redis.call("EXPIRE", long_key, long_window)
    long_ttl = long_window
end

if short_count >= short_limit then
    if short_ttl <= 0 then
        short_ttl = short_window
    end
    return {0, "short", short_ttl, short_count, long_count}
end

if long_count >= long_limit then
    if long_ttl <= 0 then
        long_ttl = long_window
    end
    return {0, "long", long_ttl, short_count, long_count}
end

short_count = redis.call("INCR", short_key)
if short_count == 1 then
    redis.call("EXPIRE", short_key, short_window)
end

long_count = redis.call("INCR", long_key)
if long_count == 1 then
    redis.call("EXPIRE", long_key, long_window)
end

return {1, "", 0, short_count, long_count}
""".strip()


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    window: str
    retry_after_seconds: int
    short_count: int
    long_count: int


class RateLimitBackendUnavailable(RuntimeError):
    pass


class RateLimitService:
    async def check_support_reply(self, user_id: int) -> RateLimitResult:
        short_key = f"support:reply:rate_limit:short:{user_id}"
        long_key = f"support:reply:rate_limit:long:{user_id}"

        try:
            redis = get_redis()
            raw = await redis.eval(
                SUPPORT_REPLY_RATE_LIMIT_LUA,
                2,
                short_key,
                long_key,
                settings.support_reply_short_rate_limit_count,
                settings.support_reply_short_rate_limit_window_seconds,
                settings.support_reply_long_rate_limit_count,
                settings.support_reply_long_rate_limit_window_seconds,
            )
        except (RedisError, RuntimeError):
            if settings.support_reply_rate_limit_fail_closed:
                raise RateLimitBackendUnavailable("Support reply rate limit backend unavailable")
            return RateLimitResult(
                allowed=True,
                window="",
                retry_after_seconds=0,
                short_count=0,
                long_count=0,
            )

        allowed, window, retry_after, short_count, long_count = raw
        return RateLimitResult(
            allowed=bool(int(allowed)),
            window=str(window or ""),
            retry_after_seconds=max(0, int(retry_after or 0)),
            short_count=int(short_count or 0),
            long_count=int(long_count or 0),
        )


rate_limit_service = RateLimitService()
