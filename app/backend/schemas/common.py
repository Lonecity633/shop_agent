from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class APIResponse(BaseModel, Generic[T]):
    code: str = "OK"
    message: str
    data: T


class PagedData(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
