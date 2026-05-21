from pydantic import BaseModel


class ProductSearchQuery(BaseModel):
    keyword: str
    limit: int = 5

