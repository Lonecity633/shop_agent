from app.core.config import settings
from app.models.user import User, UserRole
from app.services.common import ServiceError, ensure


def validate_internal_secret(secret: str) -> None:
    ensure(
        bool(secret) and secret == settings.mcp_internal_secret,
        "MCP_UNAUTHORIZED",
        "MCP 内部调用鉴权失败",
        401,
    )


def build_context_user(*, user_id: int, user_role: str) -> User:
    role = UserRole(user_role)
    return User(id=user_id, email=f"mcp-user-{user_id}@internal.local", password_hash="", role=role)


def tool_error(exc: Exception) -> dict:
    if isinstance(exc, ServiceError):
        return {"success": False, "error_code": exc.code, "message": exc.message}
    if isinstance(exc, ValueError):
        return {"success": False, "error_code": "MCP_INVALID_ARGUMENT", "message": str(exc)}
    return {"success": False, "error_code": "MCP_TOOL_ERROR", "message": "MCP 工具调用失败"}
