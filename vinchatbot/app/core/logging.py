from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

from vinchatbot.app.core.observability import get_request_id

if TYPE_CHECKING:
    from vinchatbot.app.core.config import Settings

# Standard LogRecord attributes — anything else on a record is treated as a structured "extra"
# field and serialized into the JSON line.
_RESERVED = frozenset(
    {
        "name", "msg", "args", "levelname", "levelno", "pathname", "filename", "module",
        "exc_info", "exc_text", "stack_info", "lineno", "funcName", "created", "msecs",
        "relativeCreated", "thread", "threadName", "processName", "process", "taskName",
        "message", "asctime", "request_id",
    }
)


class RequestIdFilter(logging.Filter):
    """Attach the current request-correlation id to every record (default '-')."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id() or "-"
        return True


class JsonFormatter(logging.Formatter):
    """One JSON object per log line: base fields + the request id + any `extra=` fields."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "request_id": getattr(record, "request_id", "-"),
        }
        for key, value in record.__dict__.items():
            if key in _RESERVED or key in payload:
                continue
            payload[key] = value
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def _resolve_format(settings: Settings | None) -> tuple[str, int]:
    if settings is None:
        return "text", logging.INFO
    fmt = (settings.log_format or "auto").lower()
    if fmt == "auto":
        fmt = "text" if settings.app_env.lower() == "development" else "json"
    level = getattr(logging, (settings.log_level or "INFO").upper(), logging.INFO)
    return fmt, level


def configure_logging(settings: Settings | None = None, level: int = logging.INFO) -> None:
    """Install a single root handler with the request-id filter and the chosen formatter.

    JSON in production, human-readable text in development (or whatever LOG_FORMAT forces).
    """
    fmt, resolved_level = _resolve_format(settings)
    if settings is None:
        resolved_level = level

    root = logging.getLogger()
    root.setLevel(resolved_level)
    for existing in list(root.handlers):
        root.removeHandler(existing)

    handler = logging.StreamHandler()
    handler.addFilter(RequestIdFilter())
    if fmt == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s [%(name)s] [%(request_id)s] %(message)s")
        )
    root.addHandler(handler)
