from datetime import datetime

from pydantic import BaseModel, Field


class KBDocumentCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255, description="文档标题")
    content: str = Field(..., min_length=1, description="文档正文内容")


class KBDocumentOut(BaseModel):
    id: int
    title: str
    source: str
    status: str
    chunk_count: int
    created_at: datetime


class KBRetrievalResult(BaseModel):
    chunk_id: int
    content: str
    score: float
    document_title: str
