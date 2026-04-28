import functools
import inspect
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, cast

MAIN_LOGGER_NAME = "mcp.main"
TOOLS_LOGGER_NAME = "mcp.tools"

_LOG_FORMAT = os.getenv("LOG_FORMAT", "text").lower()
_LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")


class _JsonFormatter(logging.Formatter):
    """Emit each log record as a single-line JSON object."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def _build_logging_config(fmt: str) -> dict:
    if fmt == "json":
        formatter_cfg = {"()": _JsonFormatter}
    else:
        formatter_cfg = {
            "format": "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
        }

    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {"default": formatter_cfg},
        "handlers": {
            "default": {
                "class": "logging.StreamHandler",
                "formatter": "default",
            }
        },
        "root": {
            "level": _LOG_LEVEL,
            "handlers": ["default"],
        },
    }


# Apply root logging config at import time
if _LOG_FORMAT == "json":
    logging.basicConfig(level=_LOG_LEVEL, force=True)
    root = logging.getLogger()
    for h in root.handlers:
        h.setFormatter(_JsonFormatter())
else:
    logging.basicConfig(
        level=_LOG_LEVEL,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        force=True,
    )

UVICORN_LOGGING_CONFIG = _build_logging_config(_LOG_FORMAT)

logger = logging.getLogger(TOOLS_LOGGER_NAME)


def log_tool(func):
    @functools.wraps(func)
    async def async_wrapper(*args, **kwargs):
        logger.info("Tool called: %s | kwargs=%s", func.__name__, kwargs)
        return await func(*args, **kwargs)

    cast(Any, async_wrapper).__signature__ = inspect.signature(func)
    return async_wrapper
