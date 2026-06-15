from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from app.config import settings


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        # Skip health check
        if request.url.path == "/health":
            return await call_next(request)

        # Verify device token in header
        auth_header = request.headers.get("X-Device-Token", "")
        if auth_header != settings.device_secret:
            return JSONResponse(
                status_code=401,
                content={"error": "Unauthorized: invalid device token"},
            )

        return await call_next(request)
