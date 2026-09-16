"""审计写入服务。审计失败不应回滚已经成功的业务事务。"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.models.audit import AuditEvent

logger = logging.getLogger(__name__)


def record_audit_event(
    db: Session,
    *,
    action: str,
    resource_type: str,
    actor_user_id: int | None = None,
    resource_id: int | str | None = None,
    request_id: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    """将低敏元数据加入当前事务；调用方负责统一 commit。"""
    db.add(
        AuditEvent(
            actor_user_id=actor_user_id,
            action=action,
            resource_type=resource_type,
            resource_id=str(resource_id) if resource_id is not None else None,
            request_id=request_id,
            details=details or None,
        )
    )
