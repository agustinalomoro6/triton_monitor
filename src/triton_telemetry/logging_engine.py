"""
logging_engine.py
-------------------
Formateador JSON recursivo (Integrante 3) y pipeline de logging
no bloqueante con QueueHandler/QueueListener y rotación
comprimida en .gz (Integrante 4).
"""

from __future__ import annotations

import asyncio
import datetime
import gzip
import json
import logging
import logging.handlers
import os
import queue


# =====================================================================
# INTEGRANTE 3 — Formateador JSON recursivo
# =====================================================================

_STANDARD_ATTRS = frozenset(vars(logging.LogRecord(
    name="", level=0, pathname="", lineno=0, msg="", args=(), exc_info=None
)).keys())

class RawQueueHandler(logging.handlers.QueueHandler):
    """
    QueueHandler que NO transforma el registro antes de encolarlo.
    Por defecto, QueueHandler.prepare() renderiza el mensaje a texto
    y BORRA exc_info/exc_text, destruyendo la excepcion original
    antes de que llegue al AsyncJSONFormatter. Esta version conserva
    el LogRecord intacto para que el formateador recursivo funcione.
    """
    def prepare(self, record: logging.LogRecord) -> logging.LogRecord:
        return record


class AsyncJSONFormatter(logging.Formatter):
    """
    Convierte cada LogRecord en una línea de JSON válido.

    Incluye metadatos del entorno (timestamp ISO 8601 UTC, proceso,
    hilo, tarea de asyncio) y, si el log corresponde a una excepción,
    reconstruye recursivamente el árbol completo de errores: hijos de
    un ExceptionGroup, causas (__cause__) y notas agregadas con
    .add_note().
    """

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

        # Atributos dinámicos pasados via extra={...}
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
        """
        Convierte una excepción (incluyendo ExceptionGroup) en un
        diccionario recursivo, preservando:
          - tipo y mensaje
          - notas forenses (__notes__, agregadas con .add_note())
          - la causa (__cause__), si existe
          - las excepciones hijas, si es un ExceptionGroup
        """
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


# =====================================================================
# INTEGRANTE 4 — Pipeline no bloqueante con rotación comprimida
# =====================================================================

def _gzip_namer(default_name: str) -> str:
    """
    Callback 'namer' del RotatingFileHandler: le dice qué nombre
    final debe tener el archivo rotado (le agrega .gz).
    """
    return default_name + ".gz"


def _gzip_rotator(source: str, dest: str) -> None:
    """
    Callback 'rotator': comprime el archivo de texto plano rotado
    a .gz usando la librería estándar gzip, y elimina el .txt
    residual sin comprimir.
    """
    with open(source, "rb") as f_in:
        with gzip.open(dest, "wb") as f_out:
            f_out.writelines(f_in)
    os.remove(source)


def build_logging_pipeline(
    log_path: str = "logs/triton_monitor.log",
) -> tuple[logging.handlers.QueueListener, queue.Queue]:
    """
    Arma el pipeline de logging no bloqueante:

    QueueHandler (usado por el logger, en el event loop)
        -> queue.Queue (buzón en memoria)
            -> QueueListener (en un hilo secundario)
                -> RotatingFileHandler (2 MB, hasta 3 backups, .gz)

    Devuelve el QueueListener (para poder arrancarlo/detenerlo) y
    la queue.Queue (por si se necesita inspeccionar).
    """
    os.makedirs(os.path.dirname(log_path) or ".", exist_ok=True)

    log_queue: queue.Queue = queue.Queue()

    # Handler "de verdad", el que escribe al archivo. Corre en el
    # hilo del QueueListener, nunca en el hilo/loop principal.
    file_handler = logging.handlers.RotatingFileHandler(
        log_path,
        maxBytes=2 * 1024 * 1024,  # 2 MB
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