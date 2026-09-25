
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

PROVEEDORES = {
    "AWS": "https://jsonplaceholder.typicode.com/posts/1",
    "Azure": "https://jsonplaceholder.typicode.com/posts/2",
    "GCP": "https://jsonplaceholder.typicode.com/posts/3",
}

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

    
        for tarea in tareas.values():
            resultados.append(tarea.result())

    return resultados
