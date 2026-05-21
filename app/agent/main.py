from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.agent.api.chat import router as chat_router
from app.shared.config import settings

app = FastAPI(
    title=f"{settings.app_name}-agent",
    version="0.1.0",
    description="智能客服 Agent 编排服务",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", summary="健康检查")
async def health_check():
    return {"message": "ok", "data": {"service": f"{settings.app_name}-agent", "env": settings.app_env}}


app.include_router(chat_router)

