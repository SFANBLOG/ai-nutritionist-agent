"""请求可观测性：关联 ID、低敏结构化访问日志和基础安全响应头。"""
from __future__ import annotations

import logging
import re
import time
import uuid

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings

logger = logging.getLogger("ai-nutritionist.access")
_SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{8,128}$")


class RequestContextMiddleware(BaseHTTPMiddleware):
    """为每个请求建立追踪上下文；不记录请求正文、授权头或健康数据。"""

    async def dispatch(self, request: Request, call_next):
        supplied_id = request.headers.get(settings.REQUEST_ID_HEADER, "")
        request_id = supplied_id if _SAFE_REQUEST_ID.fullmatch(supplied_id) else uuid.uuid4().hex
        request.state.request_id = request_id
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            logger.exception(
                "request_failed request_id=%s method=%s path=%s",
                request_id,
                request.method,
                request.url.path,
            )
            raise

        elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
        response.headers[settings.REQUEST_ID_HEADER] = request_id
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Cache-Control", "no-store")
        logger.info(
            "request_completed request_id=%s method=%s path=%s status=%s duration_ms=%s",
            request_id,
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
        )
        return response
