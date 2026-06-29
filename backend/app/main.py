from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.config import settings
from app.middleware.limiter import BodySizeLimitMiddleware, limiter
from app.routers import account, export, files, parse, reminders

app = FastAPI(
    title="Syllabus Parser API",
    version="0.1.0",
    description="API for parsing syllabi and exporting to calendars",
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
