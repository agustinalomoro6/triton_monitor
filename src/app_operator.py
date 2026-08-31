"""
app_operator.py
-----------------
Punto de entrada ejecutable de TritonMonitor (Integrante 5).

Arma el parser de argparse, configura el logging declarativamente
con logging.config.dictConfig, ejecuta el flujo asincrono de
core.py y captura selectivamente los errores con except* segun
la sintaxis moderna de grupos de excepciones (PEP 654).
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import logging.config
import os
import sys

# Permite ejecutar este archivo desde cualquier directorio de trabajo,
# asegurando que el paquete triton_telemetry (vecino de este archivo)
# sea siempre importable.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from triton_telemetry.core import monitorear_clusters
from triton_telemetry.exceptions import (
    CorruptedPayloadError,
    NetworkPeeringError,
    ProviderTimeoutError,
)
from triton_telemetry.logging_engine import RawQueueHandler, build_logging_pipeline
from triton_telemetry.sanitizer import validar_cluster_id, validar_timeout


def construir_parser() -> argparse.ArgumentParser:
    """Arma el parser de argparse con los validadores del Integrante 1."""
    parser = argparse.ArgumentParser(
        prog="triton_monitor",
        description="Monitor de clusters multicloud (AWS, Azure, GCP).",
    )

    parser.add_argument(
        "--cluster",
        type=validar_cluster_id,
        required=True,
        help="Identificador del cluster. Formato: cluster-<region>-<numero> "
             "(ej: cluster-us-east-01).",
    )

    parser.add_argument(
        "--timeout",
        type=validar_timeout,
        required=True,
        help="Timeout de red en segundos, estrictamente entre 0.1 y 5.0.",
    )

    parser.add_argument(
        "--log-path",
        default="logs/triton_monitor.log",
        help="Ruta del archivo de log rotativo (default: logs/triton_monitor.log).",
    )

    modo_grupo = parser.add_mutually_exclusive_group()
    modo_grupo.add_argument(
        "--debug",
        action="store_true",
        help="Modo debug: logging detallado (nivel DEBUG).",
    )
    modo_grupo.add_argument(
        "--emergency",
        action="store_true",
        help="Modo emergencia: solo errores criticos (nivel ERROR).",
    )

    return parser


def resolver_nivel_log(args: argparse.Namespace) -> int:
    """Traduce el modo elegido (nominal/debug/emergency) a un nivel de logging."""
    if args.debug:
        return logging.DEBUG
    if args.emergency:
        return logging.ERROR
    return logging.INFO  # modo nominal


def construir_dict_config(nivel: int, log_queue) -> dict:
    """
    Arma la configuracion declarativa de logging.

    El handler que de verdad escribe a disco vive del otro lado de
    la cola, dentro del QueueListener armado por build_logging_pipeline
    (logging_engine.py). Del lado de la aplicacion solo existe este
    RawQueueHandler, liviano y no bloqueante.
    """
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "handlers": {
            "queue_handler": {
                "class": "triton_telemetry.logging_engine.RawQueueHandler",
                "queue": log_queue,
            },
        },
        "loggers": {
            "triton_monitor": {
                "handlers": ["queue_handler"],
                "level": nivel,
                "propagate": False,
            },
        },
    }


async def ejecutar(args: argparse.Namespace) -> int:
    """
    Ejecuta el flujo asincrono principal y devuelve el codigo de
    salida del proceso (0 = exito, 1 = algun proveedor fallo).
    """
    logger = logging.getLogger("triton_monitor")
    codigo_salida = 0

    try:
        resultados = await monitorear_clusters(args.timeout)
        for resultado in resultados:
            logger.info(
                "Resultado final",
                extra={"cluster": args.cluster, **resultado},
            )
        print(f"[OK] Los {len(resultados)} proveedores respondieron correctamente.")

    except* ProviderTimeoutError as grupo:
        codigo_salida = 1
        for error in grupo.exceptions:
            logger.error(
                "Timeout de proveedor",
                extra={"cluster": args.cluster},
                exc_info=(type(error), error, error.__traceback__),
            )
        print(f"[ERROR] {len(grupo.exceptions)} proveedor(es) superaron el timeout.")

    except* CorruptedPayloadError as grupo:
        codigo_salida = 1
        for error in grupo.exceptions:
            logger.error(
                "Payload corrupto / error HTTP",
                extra={"cluster": args.cluster},
                exc_info=(type(error), error, error.__traceback__),
            )
        print(f"[ERROR] {len(grupo.exceptions)} proveedor(es) con error HTTP.")

    except* NetworkPeeringError as grupo:
        codigo_salida = 1
        for error in grupo.exceptions:
            logger.error(
                "Fallo de red/DNS",
                extra={"cluster": args.cluster},
                exc_info=(type(error), error, error.__traceback__),
            )
        print(f"[ERROR] {len(grupo.exceptions)} proveedor(es) con fallo de red.")

    return codigo_salida


def main() -> None:
    parser = construir_parser()
    args = parser.parse_args()

    nivel = resolver_nivel_log(args)
    listener, log_queue = build_logging_pipeline(args.log_path)
    logging.config.dictConfig(construir_dict_config(nivel, log_queue))
    listener.start()

    codigo_salida = 1
    try:
        codigo_salida = asyncio.run(ejecutar(args))
    finally:
        # Apagado ordenado: fuerza a escribir todo lo pendiente en la
        # cola antes de terminar. Sin return/break aca (PEP 765).
        listener.stop()

    sys.exit(codigo_salida)


if __name__ == "__main__":
    main()