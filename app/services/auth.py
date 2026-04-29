from datetime import UTC, datetime

from redis.exceptions import RedisError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.rate_limit import is_rate_limited
from app.core.redis_client import get_redis
from app.core.security import create_access_token, decode_access_token, get_password_hash, verify_password
from app.crud.user import create_user, get_user_by_email, get_user_by_id, update_user_profile
from app.models.user import User, UserRole
from app.schemas.auth import UserLogin, UserProfileUpdate, UserRegister
from app.services.common import ServiceError, ensure


async def resolve_current_user(db: AsyncSession, authorization: str | None) -> User:
    ensure(bool(authorization and authorization.startswith("Bearer ")), "UNAUTHORIZED", "未提供有效的访问令牌", 401)

    token = authorization.removeprefix("Bearer ").strip()
    payload = decode_access_token(token)
    ensure(bool(payload and "sub" in payload), "UNAUTHORIZED", "访问令牌无效或已过期", 401)

    jti = payload.get("jti")
    if jti:
        blacklist_key = f"{settings.redis_key_prefix}:blacklist:{jti}"
        try:
            redis = get_redis()
            if await redis.exists(blacklist_key):
                raise ServiceError("UNAUTHORIZED", "访问令牌已失效", 401)
        except (RedisError, RuntimeError):
            if settings.auth_fail_closed:
                raise ServiceError("AUTH_BACKEND_UNAVAILABLE", "鉴权服务暂不可用，请稍后再试", 503)

    try:
        user_id = int(payload["sub"])
    except (TypeError, ValueError) as exc:
        raise ServiceError("UNAUTHORIZED", "访问令牌无效", 401) from exc

    user = await get_user_by_id(db, user_id)
    ensure(user is not None, "UNAUTHORIZED", "用户不存在", 401)
    return user


async def resolve_current_user_optional(db: AsyncSession, authorization: str | None) -> User | None:
    if not authorization or not authorization.startswith("Bearer "):
        return None
    try:
        return await resolve_current_user(db=db, authorization=authorization)
    except ServiceError:
        return None


async def register_user(db: AsyncSession, payload: UserRegister) -> User:
    existing = await get_user_by_email(db, payload.email)
    ensure(existing is None, "USER_EMAIL_DUPLICATED", "邮箱已注册", 400)
    password_hash = get_password_hash(payload.password)
    return await create_user(db, email=payload.email, password_hash=password_hash, role=UserRole(payload.role))


async def login_user(db: AsyncSession, payload: UserLogin, client_ip: str) -> dict:
    rate_key = f"login:{client_ip}:{payload.email}"
    try:
        limited = await is_rate_limited(
            rate_key,
            settings.login_rate_limit_count,
            settings.login_rate_limit_window_seconds,
        )
    except RuntimeError as exc:
        raise ServiceError("AUTH_BACKEND_UNAVAILABLE", "登录限流服务暂不可用，请稍后再试", 503) from exc
    ensure(not limited, "LOGIN_RATE_LIMITED", "登录频率过高，请稍后重试", 429)

    user = await get_user_by_email(db, payload.email)
    if not user or not verify_password(payload.password, user.password_hash):
        raise ServiceError("LOGIN_FAILED", "邮箱或密码错误", 401)

    access_token = create_access_token(subject=user.id)
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": settings.jwt_access_token_expire_minutes * 60,
    }


async def logout_token(authorization: str | None) -> None:
    if not (authorization and authorization.startswith("Bearer ")):
        return

    token = authorization.removeprefix("Bearer ").strip()
    payload = decode_access_token(token)
    if not (payload and payload.get("jti") and payload.get("exp")):
        return

    exp_ts = int(payload["exp"])
    ttl = exp_ts - int(datetime.now(UTC).timestamp())
    if ttl <= 0:
        return

    try:
        redis = get_redis()
        blacklist_key = f"{settings.redis_key_prefix}:blacklist:{payload['jti']}"
        await redis.setex(blacklist_key, ttl, "1")
    except (RedisError, RuntimeError):
        if settings.auth_fail_closed:
            raise ServiceError("AUTH_BACKEND_UNAVAILABLE", "登出服务暂不可用，请稍后再试", 503)


async def update_profile(db: AsyncSession, user: User, payload: UserProfileUpdate) -> User:
    return await update_user_profile(db, user, payload)
