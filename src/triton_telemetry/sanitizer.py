"""
sanitizer.py
-------------
Validadores personalizados para argparse.

Cada función de acá se usa como `type=` en argparse. Si el dato es
inválido, lanzan argparse.ArgumentTypeError, que argparse traduce
automáticamente en un mensaje de error prolijo y en salir del
programa con código de salida 2.
"""

from __future__ import annotations

import argparse
import re

# Patrón: cluster-<region>-<numero>
# Ejemplos válidos: cluster-us-east-01, cluster-sa-east-99
_CLUSTER_PATTERN = re.compile(r"^cluster-[a-z]+-[a-z]+-\d{2,}$")

TIMEOUT_MIN = 0.1
TIMEOUT_MAX = 5.0


def validar_timeout(valor: str) -> float:
    """
    Valida que --timeout sea un float estrictamente entre 0.1 y 5.0.

    argparse siempre entrega los argumentos como texto (str), por
    eso primero intentamos convertirlo a float.
    """
    try:
        numero = float(valor)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"'{valor}' no es un número válido para --timeout."
        )

    if not (TIMEOUT_MIN < numero < TIMEOUT_MAX):
        raise argparse.ArgumentTypeError(
            f"--timeout debe estar estrictamente entre {TIMEOUT_MIN} "
            f"y {TIMEOUT_MAX} segundos (recibido: {numero})."
        )

    return numero


def validar_cluster_id(valor: str) -> str:
    """
    Valida que el ID de clúster tenga el formato
    cluster-<region>-<numero>, por ejemplo: cluster-us-east-01
    """
    if not _CLUSTER_PATTERN.match(valor):
        raise argparse.ArgumentTypeError(
            f"'{valor}' no tiene el formato esperado "
            f"'cluster-<region>-<numero>' (ej: cluster-us-east-01)."
        )

    return valor