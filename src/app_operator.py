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

    parser.add_argument(
        "--chaos",
        action="store_true",
        help="Escenario C (Inyeccion de Caos): en vez de consultar los "
             "proveedores nominales, consulta endpoints reales de "
             "httpbin.org disenhados para fallar (timeout, HTTP 504 y "
             "host inexistente), para poder demostrar en vivo los 3 "
             "tipos de error de exceptions.py.",
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
        resultados = await monitorear_clusters(args.timeout, use_chaos=args.chaos)
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


def _color(texto: str, codigo: str) -> str:
    """Envuelve texto en secuencias ANSI para colorear la terminal."""
    return f"\033[{codigo}m{texto}\033[0m"


def modo_interactivo() -> argparse.Namespace:
    """
    Interfaz interactiva que guía al usuario paso a paso cuando
    ejecuta el script sin argumentos.
    """
    print()
    print(_color("=" * 56, "35"))
    print(_color("             ⚡  B Y T E F O R C E  ⚡", "1;35"))
    print(_color("=" * 56, "35"))
    print(_color("   🔱  TRITON MONITOR  —  Modo Interactivo", "1;36"))
    print(_color("=" * 56, "36"))
    print()

    # ── 1. Cluster ID ────────────────────────────────────────
    print(_color("📌  Paso 1/5: Identificador del cluster", "1;33"))
    print("   Formato: cluster-<region>-<numero>")
    print("   Ejemplo: cluster-us-east-01, cluster-sa-east-99")
    print()
    while True:
        cluster = input(_color("   ➤ Cluster ID: ", "33")).strip()
        if not cluster:
            print(_color("   ⚠  No puede estar vacío.", "31"))
            continue
        try:
            cluster = validar_cluster_id(cluster)
            break
        except argparse.ArgumentTypeError as e:
            print(_color(f"   ⚠  {e}", "31"))
    print()

    # ── 2. Timeout ───────────────────────────────────────────
    print(_color("⏱️   Paso 2/5: Timeout de red (segundos)", "1;33"))
    print("   Rango permitido: 0.1 – 5.0 (exclusivo)")
    print("   Default: 3.0")
    print()
    while True:
        raw = input(_color("   ➤ Timeout [3.0]: ", "33")).strip()
        if not raw:
            timeout = 3.0
            break
        try:
            timeout = validar_timeout(raw)
            break
        except argparse.ArgumentTypeError as e:
            print(_color(f"   ⚠  {e}", "31"))
    print()

    # ── 3. Modo de logging ───────────────────────────────────
    print(_color("📋  Paso 3/5: Modo de logging", "1;33"))
    print("   [1] Normal  — nivel INFO (default)")
    print("   [2] Debug   — nivel DEBUG (detallado)")
    print("   [3] Emergency — nivel ERROR (solo críticos)")
    print()
    while True:
        opcion = input(_color("   ➤ Elige [1/2/3]: ", "33")).strip()
        if opcion in ("", "1"):
            debug, emergency = False, False
            break
        elif opcion == "2":
            debug, emergency = True, False
            break
        elif opcion == "3":
            debug, emergency = False, True
            break
        else:
            print(_color("   ⚠  Opción inválida. Ingresa 1, 2 o 3.", "31"))
    print()

    # ── 4. Escenario de caos (opcional) ──────────────────────
    print(_color("🌪️   Paso 4/5: Escenario de caos (opcional)", "1;33"))
    print("   Consulta endpoints reales de httpbin.org disenhados")
    print("   para fallar (timeout, HTTP 504, host inexistente),")
    print("   en vez de los proveedores nominales.")
    print()
    raw_caos = input(_color("   ➤ ¿Activar modo caos? [s/N]: ", "33")).strip().lower()
    chaos = raw_caos in ("s", "si", "sí", "y", "yes")
    print()

    # ── 5. Ruta de log ───────────────────────────────────────
    print(_color("📁  Paso 5/5: Ruta del archivo de log", "1;33"))
    default_log = "logs/triton_monitor.log"
    print(f"   Default: {default_log}")
    print()
    log_path = input(_color(f"   ➤ Log path [{default_log}]: ", "33")).strip()
    if not log_path:
        log_path = default_log
    print()

    # ── Resumen ──────────────────────────────────────────────
    modo_str = "Debug" if debug else ("Emergency" if emergency else "Normal")
    caos_str = "Sí (httpbin.org)" if chaos else "No (nominal)"
    print(_color("─" * 56, "36"))
    print(_color("  📊  Resumen de configuración:", "1;36"))
    print(f"       Cluster:   {_color(cluster, '1;37')}")
    print(f"       Timeout:   {_color(str(timeout) + 's', '1;37')}")
    print(f"       Modo log:  {_color(modo_str, '1;37')}")
    print(f"       Caos:      {_color(caos_str, '1;37')}")
    print(f"       Log path:  {_color(log_path, '1;37')}")
    print(_color("─" * 56, "36"))
    print()

    confirmar = input(_color("   ¿Ejecutar? [S/n]: ", "1;32")).strip().lower()
    if confirmar in ("n", "no"):
        print(_color("\n   ❌  Ejecución cancelada.\n", "31"))
        sys.exit(0)

    print()
    print(_color("   🚀  Iniciando monitoreo...\n", "1;32"))

    return argparse.Namespace(
        cluster=cluster,
        timeout=timeout,
        debug=debug,
        emergency=emergency,
        chaos=chaos,
        log_path=log_path,
    )


def main() -> None:
    # Si no hay argumentos en la línea de comandos → modo interactivo
    if len(sys.argv) == 1:
        args = modo_interactivo()
    else:
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