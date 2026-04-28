import json
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, field_validator


class ProductBase(BaseModel):
    name: str = Field(..., description="商品名称", min_length=1, max_length=120)
    description: str = Field("", description="商品描述")
    image_urls: list[AnyHttpUrl] = Field(default_factory=list, max_length=5, description="商品图片URL列表")
    stock: int = Field(0, ge=0, description="库存")
    price: Decimal = Field(..., gt=0, description="价格")
    category_id: int = Field(..., gt=0, description="分类ID")

    @field_validator("image_urls", mode="before")
    @classmethod
    def parse_image_urls(cls, value):
        if value is None or value == "":
            return []
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
            except json.JSONDecodeError:
                return []
            return parsed if isinstance(parsed, list) else []
        if isinstance(value, list):
            return value
        return []


class ProductCreate(ProductBase):
    pass


class ProductUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = None
    image_urls: list[AnyHttpUrl] | None = Field(default=None, max_length=5)
    stock: int | None = Field(default=None, ge=0)
    price: Decimal | None = Field(default=None, gt=0)
    category_id: int | None = Field(default=None, gt=0)

    @field_validator("image_urls", mode="before")
    @classmethod
    def parse_update_image_urls(cls, value):
        if value is None or value == "":
            return None
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
            except json.JSONDecodeError:
                return None
            return parsed if isinstance(parsed, list) else None
        if isinstance(value, list):
            return value
        return None


class ProductAuditUpdate(BaseModel):
    approval_status: Literal["approved", "rejected"] = Field(..., description="审核状态")
    review_note: str = Field(default="", description="审核备注")


class ProductOut(ProductBase):
    id: int
    seller_id: int
    approval_status: str
    category_name: str | None = None
    review_note: str
    reviewed_at: datetime | None

    model_config = ConfigDict(from_attributes=True)
