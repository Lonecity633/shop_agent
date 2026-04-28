from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AddressBase(BaseModel):
    receiver_name: str = Field(..., min_length=1, max_length=60)
    receiver_phone: str = Field(..., min_length=6, max_length=30)
    province: str = Field(..., min_length=1, max_length=60)
    city: str = Field(..., min_length=1, max_length=60)
    district: str = Field(default="", max_length=60)
    detail_address: str = Field(..., min_length=1, max_length=255)
    is_default: bool = False


class AddressCreate(AddressBase):
    pass


class AddressUpdate(BaseModel):
    receiver_name: str | None = Field(default=None, min_length=1, max_length=60)
    receiver_phone: str | None = Field(default=None, min_length=6, max_length=30)
    province: str | None = Field(default=None, min_length=1, max_length=60)
    city: str | None = Field(default=None, min_length=1, max_length=60)
    district: str | None = Field(default=None, max_length=60)
    detail_address: str | None = Field(default=None, min_length=1, max_length=255)
    is_default: bool | None = None


class AddressOut(AddressBase):
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
