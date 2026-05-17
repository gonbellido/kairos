import logging
import sys

from .trace import TraceContext


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        import json
        from datetime import datetime, timezone

        log = {
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        trace = TraceContext.snapshot()
        if trace:
            log.update(trace)
        if record.exc_info and record.exc_info[0]:
            log["exception"] = self.formatException(record.exc_info)
        return json.dumps(log, ensure_ascii=False)


def setup_json_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())
    logging.basicConfig(level=getattr(logging, level.upper(), logging.INFO), handlers=[handler])
