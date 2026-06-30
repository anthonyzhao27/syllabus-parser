"""Structured logging configuration for the backend.

Configures Python's logging via ``dictConfig`` with a JSON-ish formatter and a
configurable level. Also exposes a contextvar-backed request id so log records
emitted while handling a request can be correlated with it.
"""

import json
import logging
from contextvars import ContextVar
from logging.config import dictConfig

# Holds the current request's id so any log record can pick it up. Defaults to
# "-" when logging happens outside of a request (e.g. at startup).
request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")


def get_request_id() -> str:
    """Return the request id bound to the current context (or "-")."""
    return request_id_ctx.get()


def set_request_id(request_id: str) -> None:
    """Bind a request id to the current context."""
    request_id_ctx.set(request_id)


class RequestIdFilter(logging.Filter):
    """Injects the current request id onto every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id()
        return True


class JsonFormatter(logging.Formatter):
    """Renders log records as single-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", "-"),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def setup_logging(level: str = "INFO") -> None:
    """Configure root logging with the JSON formatter at the given level."""
    level = (level or "INFO").upper()
    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "filters": {
                "request_id": {
                    "()": "app.logging_config.RequestIdFilter",
                },
            },
            "formatters": {
                "json": {
                    "()": "app.logging_config.JsonFormatter",
                },
            },
            "handlers": {
                "default": {
                    "class": "logging.StreamHandler",
                    "formatter": "json",
                    "filters": ["request_id"],
                },
            },
            "root": {
                "handlers": ["default"],
                "level": level,
            },
            "loggers": {
                "uvicorn": {
                    "level": level,
                    "handlers": ["default"],
                    "propagate": False,
                },
                "uvicorn.error": {
                    "level": level,
                    "handlers": ["default"],
                    "propagate": False,
                },
                "uvicorn.access": {
                    "level": level,
                    "handlers": ["default"],
                    "propagate": False,
                },
            },
        }
    )
