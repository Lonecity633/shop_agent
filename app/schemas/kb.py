from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class KBDocumentCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    source: str = Field(default="", max_length=512)
    status: Literal["draft", "active", "archived"] = "active"
    content: str = Field(default="", max_length=50000)
    chunks: list[str] = Field(default_factory=list, max_length=500)


class KBDocumentOut(BaseModel):
    id: int
    title: str
    source: str
    status: str
    chunk_count: int
    created_at: datetime
    updated_at: datetime


class KBChunkOut(BaseModel):
    id: int
    document_id: int
    chunk_index: int
    content: str
    vector_id: str
    metadata: dict
    created_at: datetime
