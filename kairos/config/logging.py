import logging
import sys

from .trace import TraceContext


class StructuredFormatter(logging.Formatter):
    def __init__(self):
        super().__init__(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        )

    def format(self, record: logging.LogRecord) -> str:
        base = super().format(record)
        trace = TraceContext.snapshot()
        if trace:
            extra = " ".join(f"{k}={v}" for k, v in trace.items())
            return f"{base}  [{extra}]"
        return base


def setup_logging(level: str = "DEBUG") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(StructuredFormatter())
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.DEBUG),
        handlers=[handler],
    )
