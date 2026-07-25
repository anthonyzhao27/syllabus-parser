from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.config import settings
from app.middleware.auth import decode_jwt


def user_or_ip_key(request: Request) -> str:
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        try:
            payload = decode_jwt(auth.split(" ", 1)[1])
            sub = payload.get("sub")
            if isinstance(sub, str) and sub:
                return f"user:{sub}"
        except Exception:
            pass
    return f"ip:{get_remote_address(request)}"


# TODO: switch to Redis (storage_uri="redis://...") when scaling beyond
# one dyno. headers_enabled=False — slowapi would otherwise require a
# `response: Response` parameter on every limited endpoint.
limiter = Limiter(key_func=user_or_ip_key, headers_enabled=False)


# Uploads are multipart/form-data, so the body is the file plus form-field and
# MIME boundary overhead. Allow a 1MB margin above the file size limit to cover
# that overhead without letting the body balloon past the intended ~10MB cap.
MAX_BODY_BYTES = settings.max_file_size_mb * 1024 * 1024 + 1024 * 1024


class BodySizeLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        cl = request.headers.get("content-length")
        if cl and cl.isdigit() and int(cl) > MAX_BODY_BYTES:
            return JSONResponse(
                status_code=413,
                content={"detail": "Request body too large"},
            )
        return await call_next(request)
