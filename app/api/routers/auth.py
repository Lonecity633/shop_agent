from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from redis.exceptions import RedisError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.rate_limit import is_rate_limited
from app.core.redis_client import get_redis
from app.core.security import (
    create_access_token,
    decode_access_token,
    get_password_hash,
    verify_password,
)
from app.crud.user import create_user, get_user_by_email, get_user_by_id, update_user_profile
from app.db.session import get_db
from app.models.user import User, UserRole
from app.schemas.auth import TokenOut, UserLogin, UserOut, UserProfileUpdate, UserRegister
from app.schemas.common import APIResponse

router = APIRouter(prefix="/auth", tags=["Auth"])


async def get_current_user(
    db: AsyncSession = Depends(get_db),
    authorization: str | None = Header(default=None),
):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未提供有效的访问令牌")

    token = authorization.removeprefix("Bearer ").strip()
    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="访问令牌无效或已过期")
    jti = payload.get("jti")
    if jti:
        blacklist_key = f"{settings.redis_key_prefix}:blacklist:{jti}"
        try:
            redis = get_redis()
            if await redis.exists(blacklist_key):
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="访问令牌已失效")
        except (RedisError, RuntimeError):
            pass

    try:
        user_id = int(payload["sub"])
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="访问令牌无效") from exc

    user = await get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在")
    return user


async def get_current_user_optional(
    db: AsyncSession = Depends(get_db),
    authorization: str | None = Header(default=None),
):
    if not authorization or not authorization.startswith("Bearer "):
        return None
    try:
        return await get_current_user(db=db, authorization=authorization)
    except HTTPException:
        return None


@router.post("/register", response_model=APIResponse[UserOut], status_code=201)
async def register(payload: UserRegister, db: AsyncSession = Depends(get_db)):
    existing = await get_user_by_email(db, payload.email)
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="邮箱已注册")

    password_hash = get_password_hash(payload.password)
    user = await create_user(
        db,
        email=payload.email,
        password_hash=password_hash,
        role=UserRole(payload.role),
    )
    return {"message": "注册成功", "data": user}


@router.post("/login", response_model=APIResponse[TokenOut])
async def login(payload: UserLogin, request: Request, db: AsyncSession = Depends(get_db)):
    client_ip = request.client.host if request.client else "unknown"
    rate_key = f"login:{client_ip}:{payload.email}"
    limited = await is_rate_limited(
        rate_key,
        settings.login_rate_limit_count,
        settings.login_rate_limit_window_seconds,
    )
    if limited:
        raise HTTPException(status_code=429, detail="登录频率过高，请稍后重试")

    user = await get_user_by_email(db, payload.email)
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="邮箱或密码错误")

    access_token = create_access_token(subject=user.id)
    return {
        "message": "登录成功",
        "data": {
            "access_token": access_token,
            "token_type": "bearer",
            "expires_in": settings.jwt_access_token_expire_minutes * 60,
        },
    }


@router.post("/logout", response_model=APIResponse[dict])
async def logout(
    authorization: str | None = Header(default=None),
    _: User = Depends(get_current_user),
):
    if authorization and authorization.startswith("Bearer "):
        token = authorization.removeprefix("Bearer ").strip()
        payload = decode_access_token(token)
        if payload and payload.get("jti") and payload.get("exp"):
            exp_ts = int(payload["exp"])
            ttl = exp_ts - int(datetime.now(UTC).timestamp())
            if ttl > 0:
                try:
                    redis = get_redis()
                    blacklist_key = f"{settings.redis_key_prefix}:blacklist:{payload['jti']}"
                    await redis.setex(blacklist_key, ttl, "1")
                except (RedisError, RuntimeError):
                    pass
    return {
        "message": "登出成功，请在客户端删除本地 Token",
        "data": {"logged_out": True},
    }


@router.get("/me", response_model=APIResponse[UserOut])
async def me(current_user=Depends(get_current_user)):
    return {"message": "当前用户信息获取成功", "data": current_user}


@router.patch("/me", response_model=APIResponse[UserOut])
async def patch_me(
    payload: UserProfileUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    user = await update_user_profile(db, current_user, payload)
    return {"message": "个人资料更新成功", "data": user}
