
from __future__ import annotations

import argparse
import re

_CLUSTER_PATTERN = re.compile(r"^cluster-[a-z]+-[a-z]+-\d{2,}$")

TIMEOUT_MIN = 0.1
TIMEOUT_MAX = 5.0


def validar_timeout(valor: str) -> float:
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
   
    if not _CLUSTER_PATTERN.match(valor):
        raise argparse.ArgumentTypeError(
            f"'{valor}' no tiene el formato esperado "
            f"'cluster-<region>-<numero>' (ej: cluster-us-east-01)."
        )

    return valor
