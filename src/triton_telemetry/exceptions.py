"""
exceptions.py
--------------
Jerarquía de excepciones semánticas de TritonMonitor.

Todas heredan de Exception (NUNCA de BaseException), para que sigan
siendo capturables con `except Exception` sin interferir con señales
del sistema como KeyboardInterrupt o SystemExit.
"""

from __future__ import annotations


class TritonError(Exception):
    """
    Excepción raíz de todo el sistema TritonMonitor.

    Sirve como "paraguas" semántico: cualquier error propio de este
    proyecto hereda de acá, así se puede capturar con
    `except TritonError` si en algún punto queremos atrapar
    "cualquier falla de Triton" sin importar el tipo exacto.
    """
    pass


class ProviderTimeoutError(TritonError):
    """
    Se lanza cuando un proveedor cloud (AWS/Azure/GCP) tarda más
    del --timeout configurado en responder.

    Normalmente se relanza a partir de un httpx.TimeoutException,
    agregando contexto forense con .add_note().
    """
    pass


class CorruptedPayloadError(TritonError):
    """
    Se lanza cuando un proveedor responde, pero con un código de
    error HTTP (por ejemplo 504 o 422): el payload que llegó no es
    válido o el servidor reportó una falla.

    Normalmente se relanza con `raise CorruptedPayloadError(...) from error`
    a partir de un httpx.HTTPStatusError.
    """
    pass


class NetworkPeeringError(TritonError):
    """
    Se lanza cuando directamente no hay conectividad: falla de DNS,
    conexión rechazada, red caída, etc.
    """
    pass