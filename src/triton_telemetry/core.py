"""
core.py
--------
Lógica asíncrona de red (asyncio + httpx).

Consulta en paralelo a los 3 proveedores simulados (AWS, Azure, GCP)
usando asyncio.TaskGroup(), y traduce los fallos de httpx en las
excepciones semánticas propias de TritonMonitor.
"""

from __future__ import annotations

import asyncio
import logging

import httpx

from .exceptions import (
    CorruptedPayloadError,
    NetworkPeeringError,
    ProviderTimeoutError,
)

logger = logging.getLogger("triton_monitor")

# Los 3 "proveedores" simulados con JSONPlaceholder (operación nominal).
PROVEEDORES = {
    "AWS": "https://jsonplaceholder.typicode.com/posts/1",
    "Azure": "https://jsonplaceholder.typicode.com/posts/2",
    "GCP": "https://jsonplaceholder.typicode.com/posts/3",
}

# Endpoints reales de httpbin.org que fallan A PROPÓSITO, para poder
# demostrar en vivo (Escenario C - Inyección de Caos) los 3 tipos de
# error que existen en exceptions.py, no solo el timeout:
#   - AWS   -> tarda 3s en responder -> dispara ProviderTimeoutError
#              si --timeout es menor a eso.
#   - Azure -> responde HTTP 504     -> dispara CorruptedPayloadError.
#   - GCP   -> host inexistente      -> dispara NetworkPeeringError.
PROVEEDORES_CAOS = {
    "AWS": "https://httpbin.org/delay/3",
    "Azure": "https://httpbin.org/status/504",
    "GCP": "https://nodo-inexistente.triton-monitor.invalid",
}


async def consultar_proveedor(
    cliente: httpx.AsyncClient,
    nombre: str,
    url: str,
    timeout: float,
) -> dict:
    """
    Consulta un único proveedor cloud de forma asíncrona.

    Traduce las excepciones de bajo nivel de httpx en las excepciones
    semánticas propias del dominio de TritonMonitor.
    """
    try:
        logger.info("Consultando proveedor", extra={"proveedor": nombre, "url": url})
        respuesta = await cliente.get(url, timeout=timeout)
        respuesta.raise_for_status()
        logger.info(
            "Proveedor respondió correctamente",
            extra={"proveedor": nombre, "status_code": respuesta.status_code},
        )
        return {"proveedor": nombre, "status": "OK", "data": respuesta.json()}

    except httpx.TimeoutException as error:
        error.add_note(
            f"[Forense] El proveedor '{nombre}' superó el timeout de "
            f"{timeout}s consultando {url}."
        )
        raise ProviderTimeoutError(
            f"Timeout consultando a {nombre} ({url})"
        ) from error

    except httpx.HTTPStatusError as error:
        raise CorruptedPayloadError(
            f"{nombre} respondió con estado HTTP "
            f"{error.response.status_code} ({url})"
        ) from error

    except httpx.NetworkError as error:
        raise NetworkPeeringError(
            f"Fallo de red/DNS consultando a {nombre} ({url})"
        ) from error


async def monitorear_clusters(timeout: float, use_chaos: bool = False) -> list[dict]:
    """
    Orquesta las consultas concurrentes a los 3 proveedores dentro
    de un asyncio.TaskGroup().

    Si uno o más proveedores fallan, TaskGroup junta todas las
    excepciones en un único ExceptionGroup, que el llamador (en
    app_operator.py) debe capturar con bloques except*.

    Con use_chaos=True se consultan los endpoints reales de httpbin.org
    (PROVEEDORES_CAOS) en vez de los nominales, para poder demostrar en
    vivo los 3 tipos de fallo: timeout, HTTP 504 y fallo de DNS/red.
    """
    resultados: list[dict] = []
    endpoints = PROVEEDORES_CAOS if use_chaos else PROVEEDORES

    async with httpx.AsyncClient() as cliente:
        async with asyncio.TaskGroup() as grupo_tareas:
            tareas = {
                nombre: grupo_tareas.create_task(
                    consultar_proveedor(cliente, nombre, url, timeout)
                )
                for nombre, url in endpoints.items()
            }

        # Si llegamos acá, TaskGroup ya esperó a que todas las tareas
        # terminen (o hubiera relanzado un ExceptionGroup).
        for tarea in tareas.values():
            resultados.append(tarea.result())

    return resultados