from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.api.routers import auth
from app.core.config import settings
from app.core.redis_client import close_redis, init_redis
from app.db.init_db import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    if (
        settings.jwt_require_strong_secret
        and settings.app_env != "dev"
        and settings.jwt_secret_key == "change-this-in-production"
    ):
        raise RuntimeError("jwt_secret_key 使用了默认值，请在非开发环境中配置强密钥")

    await init_db()
    app.state.redis_available = True
    try:
        await init_redis()
    except Exception:
        app.state.redis_available = False
        if settings.auth_fail_closed:
            raise RuntimeError("Redis 初始化失败，auth_fail_closed=true，服务拒绝启动")
    yield
    await close_redis()


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="电商后端 API，面向 Agent 调用场景",
    lifespan=lifespan,
)


@app.exception_handler(HTTPException)
async def http_exception_handler(_: Request, exc: HTTPException):
    if isinstance(exc.detail, dict):
        code = exc.detail.get("code", "HTTP_ERROR")
        message = exc.detail.get("message", "请求失败")
    else:
        code = "HTTP_ERROR"
        message = str(exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": code, "message": message, "data": None},
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", summary="健康检查")
async def health_check():
    return {"message": "ok", "data": {"service": settings.app_name, "env": settings.app_env}}


app.include_router(api_router, prefix=settings.api_v1_str)
app.include_router(auth.router, prefix="/api")
