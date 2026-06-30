import logging
import os
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.logging_config import set_request_id, setup_logging
from app.config import settings
from app.middleware.limiter import BodySizeLimitMiddleware, limiter
from app.routers import account, export, files, parse, reminders

setup_logging(os.environ.get("LOG_LEVEL", "INFO"))
logger = logging.getLogger("app")

app = FastAPI(
    title="Syllabus Parser API",
    version="0.1.0",
    description="API for parsing syllabi and exporting to calendars",
    # Hide interactive docs + schema in production (no public API surface map).
    docs_url=None if settings.is_production else "/docs",
    redoc_url=None if settings.is_production else "/redoc",
    openapi_url=None if settings.is_production else "/openapi.json",
)

app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={
            "detail": "Rate limit exceeded. Please slow down and try again later."
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Log the failure with its request id and return a clean 500 (no traceback)."""
    request_id = getattr(request.state, "request_id", None)
    logger.exception(
        "Unhandled exception while processing %s %s",
        request.method,
        request.url.path,
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "request_id": request_id},
        headers={"X-Request-ID": request_id} if request_id else None,
    )


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    """Assign a request id, expose it to logs + handlers, echo it as a header."""
    request_id = str(uuid.uuid4())
    set_request_id(request_id)
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


app.add_middleware(SlowAPIMiddleware)
app.add_middleware(BodySizeLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(parse.router, prefix="/parse", tags=["parse"])
app.include_router(export.router, prefix="/export", tags=["export"])
app.include_router(reminders.router, prefix="/reminders", tags=["reminders"])
app.include_router(files.router, prefix="/files", tags=["files"])
app.include_router(account.router, prefix="/account", tags=["account"])


@app.get("/health")
async def health():
    return {"status": "ok"}
