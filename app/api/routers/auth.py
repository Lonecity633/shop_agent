from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import TokenOut, UserLogin, UserOut, UserProfileUpdate, UserRegister
from app.schemas.common import APIResponse
from app.services import auth as auth_service
from app.services.common import ServiceError

router = APIRouter(prefix="/auth", tags=["Auth"])


def _to_http_error(exc: ServiceError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.message)


async def get_current_user(
    db: AsyncSession = Depends(get_db),
    authorization: str | None = Header(default=None),
):
    try:
        return await auth_service.resolve_current_user(db, authorization)
    except ServiceError as exc:
        raise _to_http_error(exc) from exc


async def get_current_user_optional(
    db: AsyncSession = Depends(get_db),
    authorization: str | None = Header(default=None),
):
    return await auth_service.resolve_current_user_optional(db=db, authorization=authorization)


@router.post("/register", response_model=APIResponse[UserOut], status_code=201)
async def register(payload: UserRegister, db: AsyncSession = Depends(get_db)):
    try:
        user = await auth_service.register_user(db, payload)
    except ServiceError as exc:
        raise _to_http_error(exc) from exc
    return {"message": "注册成功", "data": user}


@router.post("/login", response_model=APIResponse[TokenOut])
async def login(payload: UserLogin, request: Request, db: AsyncSession = Depends(get_db)):
    client_ip = request.client.host if request.client else "unknown"
    try:
        token_data = await auth_service.login_user(db, payload, client_ip)
    except ServiceError as exc:
        raise _to_http_error(exc) from exc

    return {
        "message": "登录成功",
        "data": token_data,
    }


@router.post("/logout", response_model=APIResponse[dict])
async def logout(
    authorization: str | None = Header(default=None),
    _: User = Depends(get_current_user),
):
    try:
        await auth_service.logout_token(authorization)
    except ServiceError as exc:
        raise _to_http_error(exc) from exc
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
    user = await auth_service.update_profile(db, current_user, payload)
    return {"message": "个人资料更新成功", "data": user}
