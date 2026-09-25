
from __future__ import annotations

import asyncio
import datetime
import gzip
import json
import logging
import logging.handlers
import os
import queue

_STANDARD_ATTRS = frozenset(vars(logging.LogRecord(
    name="", level=0, pathname="", lineno=0, msg="", args=(), exc_info=None
)).keys())

class RawQueueHandler(logging.handlers.QueueHandler):

    def prepare(self, record: logging.LogRecord) -> logging.LogRecord:
        return record


class AsyncJSONFormatter(logging.Formatter):

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "process": record.process,
            "threadName": record.threadName,
            "taskName": self._get_task_name(),
        }

        for key, value in record.__dict__.items():
            if key in _STANDARD_ATTRS or key in payload:
                continue
            try:
                json.dumps(value)
                payload[key] = value
            except (TypeError, ValueError):
                payload[key] = repr(value)

        if record.exc_info:
            exc_type, exc_value, _ = record.exc_info
            if exc_value is not None:
                payload["exception"] = self._serialize_exception(exc_value)

        return json.dumps(payload, ensure_ascii=False)

    @staticmethod
    def _get_task_name() -> str | None:
        """Obtiene el nombre de la tarea asyncio actual, si existe."""
        try:
            return asyncio.current_task().get_name()
        except RuntimeError:
            return None

    def _serialize_exception(self, exc: BaseException) -> dict:

        data = {
            "type": type(exc).__name__,
            "message": str(exc),
            "notes": list(getattr(exc, "__notes__", [])),
        }

        if exc.__cause__ is not None:
            data["caused_by"] = self._serialize_exception(exc.__cause__)

        if isinstance(exc, ExceptionGroup):
            data["sub_exceptions"] = [
                self._serialize_exception(sub) for sub in exc.exceptions
            ]

        return data


def _gzip_namer(default_name: str) -> str:
    return default_name + ".gz"


def _gzip_rotator(source: str, dest: str) -> None:

    with open(source, "rb") as f_in:
        with gzip.open(dest, "wb") as f_out:
            f_out.writelines(f_in)
    os.remove(source)


def build_logging_pipeline(
    log_path: str = "logs/triton_monitor.log",
) -> tuple[logging.handlers.QueueListener, queue.Queue]:
   
    os.makedirs(os.path.dirname(log_path) or ".", exist_ok=True)

    log_queue: queue.Queue = queue.Queue()

    file_handler = logging.handlers.RotatingFileHandler(
        log_path,
        maxBytes=2 * 1024 * 1024,  
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(AsyncJSONFormatter())
    file_handler.namer = _gzip_namer
    file_handler.rotator = _gzip_rotator

    listener = logging.handlers.QueueListener(
        log_queue, file_handler, respect_handler_level=True
    )

    return listener, log_queue
