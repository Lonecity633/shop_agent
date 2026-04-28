from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.product import ProductCreate, ProductOut, ProductUpdate


class SellerProfileUpsert(BaseModel):
    shop_name: str = Field(..., min_length=2, max_length=120)
    shop_description: str = Field(default="", max_length=2000)


class SellerProfileOut(BaseModel):
    id: int
    user_id: int
    shop_name: str
    shop_description: str
    audit_status: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SellerProductCreate(ProductCreate):
    pass


class SellerProductUpdate(ProductUpdate):
    pass


class SellerProductOut(ProductOut):
    pass
