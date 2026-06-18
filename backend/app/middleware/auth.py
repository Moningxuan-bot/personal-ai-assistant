import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from app.config import settings

logger = logging.getLogger("ajiur.auth")

# 本地开发中不需要认证的路径
DEV_SKIP_AUTH_PATHS = {
    "/",
    "/health",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/favicon.ico",
}


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        # 本地开发：跳过非 API 路径的认证（方便浏览器访问 docs）
        if request.url.path in DEV_SKIP_AUTH_PATHS:
            return await call_next(request)

        # Verify device token in header
        auth_header = request.headers.get("X-Device-Token", "")
        if auth_header != settings.device_secret:
            logger.warning(
                f"Auth rejected: {request.method} {request.url.path}",
                extra={
                    "extra_fields": {
                        "method": request.method,
                        "path": request.url.path,
                    },
                },
            )
            return JSONResponse(
                status_code=401,
                content={"error": "Unauthorized: invalid device token"},
            )

        return await call_next(request)
