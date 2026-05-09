from __future__ import annotations

import json

from sqlalchemy import delete as sql_delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge import KBChunk, KBDocument


async def create_document(db: AsyncSession, title: str, source: str = "admin_upload") -> dict:
    doc = KBDocument(title=title, source=source, status="active")
    db.add(doc)
    await db.flush()
    return {"id": doc.id, "title": doc.title, "source": doc.source, "status": doc.status}


async def get_document(db: AsyncSession, document_id: int) -> dict | None:
    stmt = select(KBDocument).where(KBDocument.id == document_id)
    doc = (await db.execute(stmt)).scalar_one_or_none()
    if doc is None:
        return None
    count_stmt = select(func.count()).select_from(KBChunk).where(KBChunk.document_id == document_id)
    chunk_count = (await db.execute(count_stmt)).scalar() or 0
    return {
        "id": doc.id,
        "title": doc.title,
        "source": doc.source,
        "status": doc.status,
        "chunk_count": chunk_count,
        "created_at": doc.created_at,
    }


async def list_documents(db: AsyncSession, page: int = 1, page_size: int = 20) -> dict:
    count_stmt = select(func.count()).select_from(KBDocument)
    total = (await db.execute(count_stmt)).scalar() or 0

    chunk_count_subq = (
        select(KBChunk.document_id, func.count().label("cnt"))
        .group_by(KBChunk.document_id)
        .subquery()
    )
    data_stmt = (
        select(
            KBDocument.id,
            KBDocument.title,
            KBDocument.source,
            KBDocument.status,
            KBDocument.created_at,
            func.coalesce(chunk_count_subq.c.cnt, 0).label("chunk_count"),
        )
        .outerjoin(chunk_count_subq, chunk_count_subq.c.document_id == KBDocument.id)
        .order_by(KBDocument.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = (await db.execute(data_stmt)).all()
    items = [
        {
            "id": row[0],
            "title": row[1],
            "source": row[2],
            "status": row[3],
            "created_at": row[4],
            "chunk_count": row[5],
        }
        for row in rows
    ]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


async def create_chunks(db: AsyncSession, document_id: int, chunks: list[str]) -> list[dict]:
    records: list[dict] = []
    for idx, text in enumerate(chunks):
        chunk = KBChunk(
            document_id=document_id,
            chunk_index=idx,
            content=text,
            vector_id="",
            metadata_json=json.dumps({"document_id": document_id}, ensure_ascii=False),
        )
        db.add(chunk)
        records.append({"index": idx, "content": text})
    await db.flush()
    return records


async def get_chunks_by_ids(db: AsyncSession, chunk_ids: list[int]) -> list[dict]:
    if not chunk_ids:
        return []
    stmt = (
        select(KBChunk.id, KBChunk.content, KBChunk.document_id, KBDocument.title)
        .join(KBDocument, KBDocument.id == KBChunk.document_id)
        .where(KBChunk.id.in_(chunk_ids))
    )
    rows = (await db.execute(stmt)).all()
    return [{"chunk_id": r[0], "content": r[1], "document_id": r[2], "title": r[3]} for r in rows]


async def delete_document(db: AsyncSession, document_id: int) -> None:
    await db.execute(sql_delete(KBChunk).where(KBChunk.document_id == document_id))
    await db.execute(sql_delete(KBDocument).where(KBDocument.id == document_id))
    await db.commit()


async def log_retrieval(
    db: AsyncSession,
    *,
    session_id: int,
    message_id: int | None,
    chunk_id: int | None,
    document_id: int | None,
    score: float,
    payload: dict,
) -> None:
    from app.models.support import SupportRetrievalLog

    log = SupportRetrievalLog(
        session_id=session_id,
        message_id=message_id,
        document_id=document_id,
        chunk_id=chunk_id,
        score=score,
        is_cited=0,
        payload_json=json.dumps(payload, ensure_ascii=False),
    )
    db.add(log)
