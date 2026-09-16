"""低敏审计事件模型；用于追踪重要写操作和人工复核决策。"""
from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.sql import func

from app.core.database import Base


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id = Column(Integer, primary_key=True)
    actor_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    action = Column(String(80), nullable=False, index=True)
    resource_type = Column(String(80), nullable=False, index=True)
    resource_id = Column(String(80), nullable=True, index=True)
    request_id = Column(String(128), nullable=True, index=True)
    details = Column(JSON, nullable=True, comment="不得存储原始报告、密码、令牌或完整健康数据")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
