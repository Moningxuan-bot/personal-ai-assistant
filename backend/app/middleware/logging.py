"""
请求日志中间件。

功能：
- 从 X-Request-ID 头读取或生成 request_id
- 设置 ContextVar 供下游代码使用
- 在响应头中返回 X-Request-ID（前端可引用）
- 记录请求耗时（SSE 长连接例外：只记开始和结束事件）
- 不记录请求体（隐私保护）

注意：必须在 AuthMiddleware 之后注册，这样才能拿到通过认证的请求。
"""
import json
import logging
import time
import uuid
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from app.request_context import set_request_id, get_request_id

logger = logging.getLogger("ajiur.http")


# 这些路径不记录请求日志（太 noisy）
SKIP_LOG_PATHS = {"/health", "/docs", "/redoc", "/openapi.json", "/favicon.ico"}

# SSE/流式端点前缀
SSE_PREFIXES = ("/api/chat",)


def _is_sse_path(path: str) -> bool:
    return any(path.startswith(p) for p in SSE_PREFIXES)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        path = request.url.path

        # ---- request_id ----
        rid = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
        set_request_id(rid)

        # ---- 跳过噪音路径 ----
        if path in SKIP_LOG_PATHS:
            return await call_next(request)

        start_ms = time.time()

        if _is_sse_path(path):
            # SSE 长连接：只记开始，不记结束（结束由 ChatService 内记）
            logger.info(
                "SSE stream started",
                extra={"extra_fields": {"method": request.method, "path": path}},
            )
            response = await call_next(request)
            response.headers["X-Request-ID"] = rid
            return response

        # ---- 普通 HTTP 请求 ----
        response = await call_next(request)

        elapsed_ms = round((time.time() - start_ms) * 1000)
        # 提取 extra_fields，确保合并进去
        extra_fields = {
            "method": request.method,
            "path": path,
            "status": response.status_code,
            "elapsed_ms": elapsed_ms,
        }
        level = logging.WARNING if response.status_code >= 500 else logging.INFO
        logger.log(
            level,
            f"{request.method} {path} → {response.status_code} {elapsed_ms}ms",
            extra={"extra_fields": extra_fields},
        )

        response.headers["X-Request-ID"] = rid
        return response
