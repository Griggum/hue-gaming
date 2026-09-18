import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


class JsonFormatter(logging.Formatter):
    def format(self, record):
        return json.dumps(
            {
                "time": self.formatTime(record),
                "level": record.levelname,
                "event": record.getMessage(),
            }
        )


def configure(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(path, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger("wow_hue")
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
