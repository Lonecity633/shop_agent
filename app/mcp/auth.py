from app.shared.config import settings


def validate_internal_secret(secret: str) -> None:
    if not secret or secret != settings.mcp_internal_secret:
        raise PermissionError("MCP 内部调用鉴权失败")


def tool_error(exc: Exception) -> dict:
    return {"success": False, "data": None, "error": exc.__class__.__name__}
