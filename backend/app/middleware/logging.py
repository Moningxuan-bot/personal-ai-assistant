"""
请求日志中间件。

功能：
- 从 X-Request-ID 头读取或生成 request_id
- 设置 ContextVar 供下游代码使用（finally 中 reset，防止残留）
- 在响应头中返回 X-Request-ID（前端可引用）
- 记录请求耗时（SSE 长连接例外：仅成功时记 start，结束由 ChatService 内记）
- 不记录请求体（隐私保护）

注意：必须在 AuthMiddleware 之后注册，这样才能拿到通过认证的请求。
"""
import logging
import time
import uuid
from starlette.middleware.base import BaseHTTPMiddleware
from app.request_context import request_id, set_request_id

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
        token = set_request_id(rid)

        try:
            # ---- 跳过噪音路径 ----
            if path in SKIP_LOG_PATHS:
                response = await call_next(request)
                return response

            start_ms = time.time()

            if _is_sse_path(path):
                # SSE: 先让 auth 等中间件跑完，只有 2xx 才记 start
                response = await call_next(request)
                if response.status_code < 400:
                    logger.info(
                        "SSE stream started",
                        extra={"extra_fields": {"method": request.method, "path": path}},
                    )
                else:
                    # 401/403 等按普通请求记录
                    elapsed_ms = round((time.time() - start_ms) * 1000)
                    logger.warning(
                        f"{request.method} {path} → {response.status_code} {elapsed_ms}ms (SSE rejected)",
                        extra={
                            "extra_fields": {
                                "method": request.method,
                                "path": path,
                                "status": response.status_code,
                                "elapsed_ms": elapsed_ms,
                            },
                        },
                    )
                response.headers["X-Request-ID"] = rid
                return response

            # ---- 普通 HTTP 请求 ----
            try:
                response = await call_next(request)
                status = response.status_code
                error_type = None
            except Exception as e:
                status = 500
                error_type = type(e).__name__
                raise
            finally:
                elapsed_ms = round((time.time() - start_ms) * 1000)
                extra_fields = {
                    "method": request.method,
                    "path": path,
                    "status": status,
                    "elapsed_ms": elapsed_ms,
                }
                if error_type:
                    extra_fields["error_type"] = error_type
                    logger.error(
                        f"{request.method} {path} → request_failed {elapsed_ms}ms error={error_type}",
                        extra={"extra_fields": extra_fields},
                    )
                else:
                    level = logging.WARNING if status >= 500 else logging.INFO
                    logger.log(
                        level,
                        f"{request.method} {path} → {status} {elapsed_ms}ms",
                        extra={"extra_fields": extra_fields},
                    )

            response.headers["X-Request-ID"] = rid
            return response

        finally:
            request_id.reset(token)
