from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.product import ProductOut


class CartItemCreate(BaseModel):
    product_id: int = Field(..., gt=0)
    quantity: int = Field(default=1, ge=1, le=99)


class CartItemUpdate(BaseModel):
    quantity: int | None = Field(default=None, ge=1, le=99)
    selected: bool | None = None


class CartItemOut(BaseModel):
    id: int
    user_id: int
    product_id: int
    quantity: int
    selected: bool
    created_at: datetime
    updated_at: datetime
    product: ProductOut

    model_config = ConfigDict(from_attributes=True)
