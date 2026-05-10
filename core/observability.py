import logging
import time
import uuid
from contextvars import ContextVar
from typing import Any, Dict, Optional

request_id_var: ContextVar[str] = ContextVar("request_id", default="")


class RequestIdFilter(logging.Filter):
    """Injects the current request ID into log records."""
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get() or "-"
        return True


def setup_logging(log_level: str = "INFO") -> None:
    """Configure structured logging with request IDs."""
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | request_id=%(request_id)s | %(name)s | %(message)s"
    )
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    handler.addFilter(RequestIdFilter())
    
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level.upper())
    root_logger.handlers = []
    root_logger.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance."""
    return logging.getLogger(name)


def set_request_id(request_id: Optional[str] = None) -> str:
    """Set or generate a request ID for the current context."""
    rid = request_id or str(uuid.uuid4())
    request_id_var.set(rid)
    return rid


class Timer:
    """Context manager for timing code blocks."""
    def __init__(self, name: str, logger: Optional[logging.Logger] = None):
        self.name = name
        self.logger = logger or get_logger("timer")
        self.start: Optional[float] = None
        self.elapsed_ms: Optional[float] = None

    def __enter__(self) -> "Timer":
        self.start = time.perf_counter()
        return self

    def __exit__(self, *args: Any) -> None:
        if self.start is not None:
            self.elapsed_ms = (time.perf_counter() - self.start) * 1000
            self.logger.info(
                "timer",
                extra={
                    "timer_name": self.name,
                    "elapsed_ms": round(self.elapsed_ms, 2),
                },
            )
