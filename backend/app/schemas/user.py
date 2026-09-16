"""用户相关 Pydantic 模式"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.user import Gender


class UserBase(BaseModel):
    username: str = Field(..., min_length=2, max_length=50, description="用户名")
    email: EmailStr = Field(..., description="邮箱")
    full_name: Optional[str] = Field(None, max_length=100)
    phone: Optional[str] = Field(None, max_length=20)
    age: Optional[int] = Field(None, ge=0, le=150)
    gender: Optional[Gender] = None
    height: Optional[float] = Field(None, ge=0, le=300, description="身高 cm")
    weight: Optional[float] = Field(None, ge=0, le=500, description="体重 kg")


class UserCreate(UserBase):
    """用户注册"""

    password: str = Field(..., min_length=6, max_length=128)


class UserUpdate(BaseModel):
    """用户资料更新"""

    full_name: Optional[str] = None
    phone: Optional[str] = None
    age: Optional[int] = Field(None, ge=0, le=150)
    gender: Optional[Gender] = None
    height: Optional[float] = Field(None, ge=0, le=300)
    weight: Optional[float] = Field(None, ge=0, le=500)
    password: Optional[str] = Field(None, min_length=6, max_length=128)


class UserResponse(BaseModel):
    """用户信息响应"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: EmailStr
    full_name: Optional[str] = None
    phone: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[Gender] = None
    height: Optional[float] = None
    weight: Optional[float] = None
    is_active: bool = True
    is_superuser: bool = False
    created_at: Optional[datetime] = None
    # 派生指标
    bmi: Optional[float] = None


class Token(BaseModel):
    """登录令牌"""

    access_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    sub: Optional[str] = None
    exp: Optional[int] = None
