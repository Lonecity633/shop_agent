from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CategoryOut(BaseModel):
    id: int
    name: str
    sort_order: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CategoryCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    sort_order: int = Field(default=100, ge=0, le=9999)
    is_active: bool = True

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        name = value.strip()
        if not name:
            raise ValueError("分类名称不能为空")
        return name


class CategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    sort_order: int | None = Field(default=None, ge=0, le=9999)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        name = value.strip()
        if not name:
            raise ValueError("分类名称不能为空")
        return name


class CategoryStatusUpdate(BaseModel):
    is_active: bool
