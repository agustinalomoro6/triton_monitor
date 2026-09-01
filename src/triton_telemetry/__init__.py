"""
triton_telemetry
------------------
Paquete de telemetría de TritonMonitor.

Expone la API pública del proyecto para que pueda importarse de forma
limpia desde afuera, por ejemplo:

    from triton_telemetry import (
        monitorear_clusters,
        TritonError,
        ProviderTimeoutError,
        CorruptedPayloadError,
        NetworkPeeringError,
        validar_timeout,
        validar_cluster_id,
        AsyncJSONFormatter,
        RawQueueHandler,
        build_logging_pipeline,
    )
"""

from __future__ import annotations

from .core import PROVEEDORES, monitorear_clusters
from .exceptions import (
    CorruptedPayloadError,
    NetworkPeeringError,
    ProviderTimeoutError,
    TritonError,
)
from .logging_engine import (
    AsyncJSONFormatter,
    RawQueueHandler,
    build_logging_pipeline,
)
from .sanitizer import validar_cluster_id, validar_timeout

__all__ = [
    # core.py — Integrante 2
    "monitorear_clusters",
    "PROVEEDORES",
    # exceptions.py — Integrante 1
    "TritonError",
    "ProviderTimeoutError",
    "CorruptedPayloadError",
    "NetworkPeeringError",
    # sanitizer.py — Integrante 1
    "validar_timeout",
    "validar_cluster_id",
    # logging_engine.py — Integrantes 3 y 4
    "AsyncJSONFormatter",
    "RawQueueHandler",
    "build_logging_pipeline",
]
