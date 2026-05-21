from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class UserRegister(BaseModel):
    email: EmailStr = Field(..., description="邮箱")
    password: str = Field(..., min_length=8, max_length=128, description="明文密码")
    role: Literal["buyer", "seller"] = Field(default="buyer", description="用户角色")


class UserLogin(BaseModel):
    email: EmailStr = Field(..., description="登录邮箱")
    password: str = Field(..., min_length=8, max_length=128)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class UserOut(BaseModel):
    id: int
    email: str
    role: str
    display_name: str | None
    phone: str | None
    avatar_url: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserProfileUpdate(BaseModel):
    display_name: str | None = Field(default=None, max_length=60)
    phone: str | None = Field(default=None, max_length=30)
    avatar_url: str | None = Field(default=None, max_length=512)

    @field_validator("display_name", "phone", "avatar_url")
    @classmethod
    def strip_value(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None
