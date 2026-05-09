from __future__ import annotations

import json
import logging

from sqlalchemy import delete as sql_delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.retrieval.client import ChromaClient
from app.agent.retrieval.embedding import EmbeddingService
from app.agent.retrieval.splitter import split_text
from app.core.config import settings
from app.models.knowledge import KBChunk, KBDocument

logger = logging.getLogger(__name__)

_chroma_client: ChromaClient | None = None
_embedding_service: EmbeddingService | None = None


def _get_chroma() -> ChromaClient:
    global _chroma_client
    if _chroma_client is None:
        _chroma_client = ChromaClient()
    return _chroma_client


def _get_embedding() -> EmbeddingService:
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service


async def retrieve(db: AsyncSession, query: str, top_k: int | None = None) -> list[dict]:
    if top_k is None:
        top_k = settings.support_retrieval_top_k

    embedding_svc = _get_embedding()
    chroma = _get_chroma()

    query_embedding = await embedding_svc.embed_query(query)
    raw_results = await chroma.query(query_embedding, top_k)

    if not raw_results:
        return []

    chunk_ids = [r["chunk_id"] for r in raw_results]
    stmt = (
        select(KBChunk.id, KBChunk.content, KBChunk.document_id, KBDocument.title)
        .join(KBDocument, KBDocument.id == KBChunk.document_id)
        .where(KBChunk.id.in_(chunk_ids))
    )
    rows = (await db.execute(stmt)).all()
    chunk_map = {row[0]: {"content": row[1], "document_id": row[2], "title": row[3]} for row in rows}

    score_map = {r["chunk_id"]: r["distance"] for r in raw_results}
    results = []
    for cid in chunk_ids:
        info = chunk_map.get(cid)
        if info:
            distance = score_map.get(cid, 1.0)
            score = max(0.0, 1.0 - distance)
            results.append({
                "chunk_id": cid,
                "content": info["content"],
                "score": round(score, 4),
                "document_title": info["title"],
                "document_id": info["document_id"],
            })
    return results


async def ingest_document(db: AsyncSession, title: str, content: str) -> dict:
    doc = KBDocument(title=title, source="admin_upload", status="active")
    db.add(doc)
    await db.flush()

    chunks_text = split_text(content)
    if not chunks_text:
        await db.commit()
        return {"document_id": doc.id, "chunk_count": 0}

    embedding_svc = _get_embedding()
    embeddings = await embedding_svc.embed(chunks_text)

    chunk_records: list[KBChunk] = []
    for idx, text in enumerate(chunks_text):
        chunk = KBChunk(
            document_id=doc.id,
            chunk_index=idx,
            content=text,
            vector_id="",
            metadata_json="{}",
        )
        db.add(chunk)
        chunk_records.append(chunk)

    await db.flush()

    chroma = _get_chroma()
    vector_ids = [str(c.id) for c in chunk_records]
    await chroma.upsert_chunks(
        chunk_ids=vector_ids,
        texts=chunks_text,
        embeddings=embeddings,
    )

    for c, vid in zip(chunk_records, vector_ids):
        c.vector_id = vid
        c.metadata_json = json.dumps({"document_id": doc.id}, ensure_ascii=False)

    await db.commit()
    return {"document_id": doc.id, "chunk_count": len(chunk_records)}


async def delete_document(db: AsyncSession, document_id: int) -> None:
    chroma = _get_chroma()
    await chroma.delete_by_document(document_id)

    await db.execute(sql_delete(KBChunk).where(KBChunk.document_id == document_id))
    await db.execute(sql_delete(KBDocument).where(KBDocument.id == document_id))
    await db.commit()
