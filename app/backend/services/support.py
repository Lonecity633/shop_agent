from sqlalchemy.ext.asyncio import AsyncSession

import time

from app.backend.clients.agent_client import AgentAPIClient, AgentAPIClientError
from app.backend.repositories import support as support_crud
from app.backend.models.user import User, UserRole
from app.backend.schemas.support import SupportAutoReplyRequest, SupportMessageCreate, SupportMySessionCreate, SupportSessionCreate
from app.backend.services.rate_limit import RateLimitBackendUnavailable, rate_limit_service
from app.backend.services.common import ServiceError, ensure
from app.shared.logging import get_logger

logger = get_logger(__name__)


def ensure_support_or_admin(current_user: User) -> None:
    ensure(current_user.role == UserRole.admin, "ROLE_DENIED", "仅管理员可访问客服聚合接口", 403)


async def get_user_overview(db: AsyncSession, current_user: User, user_id: int):
    ensure_support_or_admin(current_user)
    try:
        return await support_crud.get_user_overview(db, user_id)
    except ValueError as exc:
        raise ServiceError("USER_NOT_FOUND", str(exc), 404) from exc


async def get_order_timeline(db: AsyncSession, current_user: User, order_id: int):
    ensure_support_or_admin(current_user)
    try:
        return await support_crud.get_order_timeline(db, order_id)
    except ValueError as exc:
        raise ServiceError("ORDER_NOT_FOUND", str(exc), 404) from exc


async def create_support_session(db: AsyncSession, current_user: User, payload: SupportSessionCreate):
    ensure_support_or_admin(current_user)
    try:
        return await support_crud.create_support_session(db, current_user.id, payload)
    except ValueError as exc:
        raise ServiceError("USER_NOT_FOUND", str(exc), 404) from exc


async def create_support_message(db: AsyncSession, current_user: User, session_id: int, payload: SupportMessageCreate):
    session = await support_crud.get_support_session(db, session_id)
    if session is None:
        raise ServiceError("SUPPORT_SESSION_NOT_FOUND", "会话不存在", 404)
    _ensure_session_access(current_user, session.user_id)
    try:
        return await support_crud.create_support_message(db, session_id, payload)
    except ValueError as exc:
        status_code = 404 if "会话不存在" in str(exc) else 400
        raise ServiceError("SUPPORT_MESSAGE_CREATE_FAILED", str(exc), status_code) from exc


async def get_support_messages(db: AsyncSession, current_user: User, session_id: int):
    session = await support_crud.get_support_session(db, session_id)
    if session is None:
        raise ServiceError("SUPPORT_SESSION_NOT_FOUND", "会话不存在", 404)
    _ensure_session_access(current_user, session.user_id)
    try:
        return await support_crud.list_support_messages(db, session_id)
    except ValueError as exc:
        raise ServiceError("SUPPORT_SESSION_NOT_FOUND", str(exc), 404) from exc


async def auto_reply(
    db: AsyncSession,
    current_user: User,
    session_id: int,
    payload: SupportAutoReplyRequest,
):
    started_at = time.perf_counter()
    try:
        session = await support_crud.get_support_session(db, session_id)
        if session is None:
            raise ServiceError("SUPPORT_SESSION_NOT_FOUND", "会话不存在", 404)
        _ensure_session_access(current_user, session.user_id)

        rate_limit = await rate_limit_service.check_support_reply(current_user.id)
        logger.info(
            "support_reply_rate_limit_checked session_id=%s user_id=%s allowed=%s window=%s short_count=%s long_count=%s",
            session_id,
            current_user.id,
            rate_limit.allowed,
            rate_limit.window,
            rate_limit.short_count,
            rate_limit.long_count,
        )
        if not rate_limit.allowed:
            raise ServiceError(
                "SUPPORT_REPLY_RATE_LIMITED",
                "您发送消息太频繁，请稍后再试",
                429,
            )

        user_message = await support_crud.create_support_message(
            db,
            session_id,
            SupportMessageCreate(role="user", content=payload.content),
        )
        logger.info(
            "support_reply_user_message_saved session_id=%s user_id=%s message_id=%s message_len=%s",
            session_id,
            current_user.id,
            user_message["message"].id,
            len(payload.content),
        )

        agent_status = "success"
        try:
            agent_response = await AgentAPIClient().chat(
                user_id=current_user.id,
                session_id=str(session_id),
                message=payload.content,
            )
        except AgentAPIClientError as exc:
            agent_status = "failed"
            duration_ms = int((time.perf_counter() - started_at) * 1000)
            logger.exception(
                "support_reply_agent_failed session_id=%s user_id=%s agent_status=%s duration_ms=%s",
                session_id,
                current_user.id,
                agent_status,
                duration_ms,
            )
            raise ServiceError("AGENT_SERVICE_UNAVAILABLE", str(exc), 503) from exc

        answer = str(agent_response.get("answer") or "智能客服暂时没有生成回复，请稍后再试。")
        route = str(agent_response.get("route") or "unknown")
        tool_calls = agent_response.get("tool_calls")
        evidences = tool_calls if isinstance(tool_calls, list) else []

        assistant_message = await support_crud.create_support_message(
            db,
            session_id,
            SupportMessageCreate(role="assistant", content=answer),
        )
        duration_ms = int((time.perf_counter() - started_at) * 1000)
        logger.info(
            "support_reply_completed session_id=%s user_id=%s agent_status=%s route=%s assistant_message_id=%s duration_ms=%s",
            session_id,
            current_user.id,
            agent_status,
            route,
            assistant_message["message"].id,
            duration_ms,
        )
        return {
            "answer": answer,
            "route": route,
            "resolved_seller_id": None,
            "evidences": evidences,
            "support_ticket": None,
        }
    except RateLimitBackendUnavailable as exc:
        raise ServiceError("SUPPORT_RATE_LIMIT_UNAVAILABLE", "客服限流服务暂不可用，请稍后再试", 503) from exc
    except ValueError as exc:
        raise ServiceError("SUPPORT_SESSION_NOT_FOUND", str(exc), 404) from exc
    except PermissionError as exc:
        raise ServiceError("SUPPORT_SESSION_FORBIDDEN", str(exc), 403) from exc


async def create_my_support_session(
    db: AsyncSession,
    current_user: User,
    payload: SupportMySessionCreate,
):
    ensure(current_user.role in (UserRole.buyer, UserRole.seller), "ROLE_DENIED", "仅买家或卖家可发起客服会话", 403)
    return await support_crud.create_support_session_for_user(
        db,
        user_id=current_user.id,
        question=payload.question,
        queried_entities=payload.queried_entities,
    )


async def get_my_latest_support_session(
    db: AsyncSession,
    current_user: User,
):
    ensure(current_user.role in (UserRole.buyer, UserRole.seller), "ROLE_DENIED", "仅买家或卖家可访问客服会话", 403)
    data = await support_crud.get_latest_support_session_for_user(db, current_user.id)
    if data is None:
        raise ServiceError("SUPPORT_SESSION_NOT_FOUND", "暂无历史会话", 404)
    return data


def _ensure_session_access(current_user: User, session_user_id: int) -> None:
    if current_user.role == UserRole.admin:
        return
    if current_user.role in (UserRole.buyer, UserRole.seller) and current_user.id == session_user_id:
        return
    raise ServiceError("SUPPORT_SESSION_FORBIDDEN", "当前用户无权访问该会话", 403)
