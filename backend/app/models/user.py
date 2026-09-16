"""用户数据模型"""
import enum

from sqlalchemy import Boolean, Column, DateTime, Enum as SAEnum, Float, Integer, String
from sqlalchemy.sql import func

from app.core.database import Base


class Gender(str, enum.Enum):
    """性别枚举"""

    MALE = "male"
    FEMALE = "female"
    OTHER = "other"


class User(Base):
    """用户表模型"""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False, comment="用户名")
    email = Column(String(100), unique=True, index=True, nullable=False, comment="邮箱")
    hashed_password = Column(String(255), nullable=False, comment="密码哈希")
    full_name = Column(String(100), comment="真实姓名")
    phone = Column(String(20), comment="手机号")
    age = Column(Integer, comment="年龄")
    gender = Column(
        SAEnum(Gender, native_enum=False, values_callable=lambda e: [m.value for m in e]),
        comment="性别",
    )
    height = Column(Float, comment="身高(cm)")
    weight = Column(Float, comment="体重(kg)")
    is_active = Column(Boolean, default=True, comment="是否激活")
    is_superuser = Column(Boolean, default=False, comment="是否管理员")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
