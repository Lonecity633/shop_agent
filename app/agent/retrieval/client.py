from __future__ import annotations

import asyncio

import chromadb

from app.core.config import settings


class ChromaClient:
    def __init__(self) -> None:
        self._client = chromadb.PersistentClient(path=settings.support_chroma_persist_dir)
        self._collection = self._client.get_or_create_collection(
            name=settings.support_chroma_collection,
            metadata={"hnsw:space": "cosine"},
        )

    def _upsert_sync(self, chunk_ids: list[str], texts: list[str], embeddings: list[list[float]]) -> None:
        self._collection.upsert(ids=chunk_ids, documents=texts, embeddings=embeddings)

    async def upsert_chunks(self, chunk_ids: list[str], texts: list[str], embeddings: list[list[float]]) -> None:
        await asyncio.to_thread(self._upsert_sync, chunk_ids, texts, embeddings)

    def _query_sync(self, embedding: list[float], top_k: int) -> dict:
        return self._collection.query(query_embeddings=[embedding], n_results=top_k)

    async def query(self, embedding: list[float], top_k: int) -> list[dict]:
        result = await asyncio.to_thread(self._query_sync, embedding, top_k)
        ids = result.get("ids", [[]])[0]
        documents = result.get("documents", [[]])[0]
        distances = result.get("distances", [[]])[0]
        return [
            {"chunk_id": int(cid), "content": doc, "distance": dist}
            for cid, doc, dist in zip(ids, documents, distances)
        ]

    def _delete_sync(self, where: dict) -> None:
        self._collection.delete(where=where)

    async def delete_by_document(self, document_id: int) -> None:
        await asyncio.to_thread(self._delete_sync, {"document_id": document_id})
