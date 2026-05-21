from __future__ import annotations

import json
import logging
import re

from sqlalchemy import delete as sql_delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.backend.knowledge.embedding import EmbeddingService
from app.backend.knowledge.splitter import split_text
from app.backend.knowledge.vector_client import ChromaClient
from app.backend.models.knowledge import KBChunk, KBDocument
from app.shared.config import settings

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

    try:
        query_embedding = await _get_embedding().embed_query(query)
        raw_results = await _get_chroma().query(query_embedding, top_k)
    except Exception:
        logger.exception("向量检索失败，降级到数据库关键词检索")
        return await keyword_retrieve(db, query, top_k=top_k)

    if not raw_results:
        return await keyword_retrieve(db, query, top_k=top_k)

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
            results.append(
                {
                    "chunk_id": cid,
                    "content": info["content"],
                    "score": round(max(0.0, 1.0 - distance), 4),
                    "document_title": info["title"],
                    "document_id": info["document_id"],
                }
            )
    return results


async def keyword_retrieve(db: AsyncSession, query: str, top_k: int | None = None) -> list[dict]:
    if top_k is None:
        top_k = settings.support_retrieval_top_k
    limit = max(1, min(int(top_k), 10))

    tokens = _extract_query_tokens(query)
    stmt = (
        select(KBChunk.id, KBChunk.content, KBChunk.document_id, KBDocument.title)
        .join(KBDocument, KBDocument.id == KBChunk.document_id)
        .where(KBDocument.status == "active")
    )
    if tokens:
        conditions = []
        for token in tokens:
            pattern = f"%{token}%"
            conditions.append(KBChunk.content.like(pattern))
            conditions.append(KBDocument.title.like(pattern))
        stmt = stmt.where(or_(*conditions))

    rows = (await db.execute(stmt.order_by(KBDocument.id.desc(), KBChunk.chunk_index.asc()).limit(limit))).all()
    if not rows and tokens:
        rows = (
            await db.execute(
                select(KBChunk.id, KBChunk.content, KBChunk.document_id, KBDocument.title)
                .join(KBDocument, KBDocument.id == KBChunk.document_id)
                .where(KBDocument.status == "active")
                .order_by(KBDocument.id.desc(), KBChunk.chunk_index.asc())
                .limit(limit)
            )
        ).all()

    return [
        {
            "chunk_id": row[0],
            "content": row[1],
            "score": _keyword_score(row[1], row[3], tokens),
            "document_title": row[3],
            "document_id": row[2],
        }
        for row in rows
    ]


async def ingest_document(db: AsyncSession, title: str, content: str) -> dict:
    doc = KBDocument(title=title, source="admin_upload", status="active")
    db.add(doc)
    await db.flush()

    chunks_text = split_text(content)
    if not chunks_text:
        await db.commit()
        return {"document_id": doc.id, "chunk_count": 0}

    embeddings = await _get_embedding().embed(chunks_text)
    chunk_records: list[KBChunk] = []
    for idx, text in enumerate(chunks_text):
        chunk = KBChunk(document_id=doc.id, chunk_index=idx, content=text, vector_id="", metadata_json="{}")
        db.add(chunk)
        chunk_records.append(chunk)

    await db.flush()
    vector_ids = [str(c.id) for c in chunk_records]
    await _get_chroma().upsert_chunks(chunk_ids=vector_ids, texts=chunks_text, embeddings=embeddings)

    for chunk, vector_id in zip(chunk_records, vector_ids):
        chunk.vector_id = vector_id
        chunk.metadata_json = json.dumps({"document_id": doc.id}, ensure_ascii=False)

    await db.commit()
    return {"document_id": doc.id, "chunk_count": len(chunk_records)}


async def delete_document(db: AsyncSession, document_id: int) -> None:
    await _get_chroma().delete_by_document(document_id)
    await db.execute(sql_delete(KBChunk).where(KBChunk.document_id == document_id))
    await db.execute(sql_delete(KBDocument).where(KBDocument.id == document_id))
    await db.commit()


def _extract_query_tokens(query: str) -> list[str]:
    text = re.sub(r"[，。！？、,.!?;；:：()\[\]【】\"'“”‘’\s]+", " ", query.strip())
    candidates = [item for item in text.split(" ") if item]
    stopwords = {"我", "想", "问", "一下", "请问", "咨询", "平台", "规则", "政策", "相关", "是什么", "有哪些", "怎么", "如何", "可以", "吗"}
    tokens = []
    for item in candidates:
        cleaned = item.strip()
        if cleaned not in stopwords and len(cleaned) >= 2:
            tokens.append(cleaned)
    return tokens[:6]


def _keyword_score(content: str, title: str, tokens: list[str]) -> float:
    if not tokens:
        return 0.25
    hit_count = sum(1 for token in tokens if token in content or token in title)
    return round(min(0.8, 0.3 + hit_count * 0.1), 4)

