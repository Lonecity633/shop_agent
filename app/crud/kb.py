from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.kb import KBChunk, KBDocument, KBDocumentStatus
from app.schemas.kb import KBDocumentCreate


def _split_content(content: str) -> list[str]:
    parts = [part.strip() for part in content.split("\n\n")]
    return [part for part in parts if part]


async def create_document(db: AsyncSession, payload: KBDocumentCreate) -> dict:
    document = KBDocument(
        title=payload.title.strip(),
        source=payload.source.strip(),
        status=KBDocumentStatus(payload.status),
    )
    db.add(document)
    await db.flush()

    chunk_texts = [item.strip() for item in payload.chunks if item and item.strip()]
    if not chunk_texts and payload.content.strip():
        chunk_texts = _split_content(payload.content.strip())

    for idx, chunk in enumerate(chunk_texts, start=1):
        db.add(
            KBChunk(
                document_id=document.id,
                chunk_index=idx,
                content=chunk,
                vector_id="",
                metadata_json="{}",
            )
        )

    await db.commit()
    await db.refresh(document)
    return {
        "id": document.id,
        "title": document.title,
        "source": document.source,
        "status": document.status.value,
        "chunk_count": len(chunk_texts),
        "created_at": document.created_at,
        "updated_at": document.updated_at,
    }


async def list_documents(
    db: AsyncSession,
    *,
    status: str | None = None,
    keyword: str | None = None,
    limit: int = 50,
) -> list[dict]:
    chunk_count_subquery = (
        select(KBChunk.document_id, func.count(KBChunk.id).label("chunk_count"))
        .group_by(KBChunk.document_id)
        .subquery()
    )

    stmt = (
        select(
            KBDocument,
            func.coalesce(chunk_count_subquery.c.chunk_count, 0).label("chunk_count"),
        )
        .outerjoin(chunk_count_subquery, chunk_count_subquery.c.document_id == KBDocument.id)
        .order_by(KBDocument.id.desc())
        .limit(limit)
    )
    if status:
        try:
            stmt = stmt.where(KBDocument.status == KBDocumentStatus(status))
        except ValueError:
            return []
    if keyword:
        stmt = stmt.where(KBDocument.title.ilike(f"%{keyword.strip()}%"))

    rows = (await db.execute(stmt)).all()
    return [
        {
            "id": row.KBDocument.id,
            "title": row.KBDocument.title,
            "source": row.KBDocument.source,
            "status": row.KBDocument.status.value,
            "chunk_count": int(row.chunk_count or 0),
            "created_at": row.KBDocument.created_at,
            "updated_at": row.KBDocument.updated_at,
        }
        for row in rows
    ]
