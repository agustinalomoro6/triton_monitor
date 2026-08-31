"""
forensic_check.py
-------------------
Integrante 6 - Script forense de certificacion de logs.

Descomprime los archivos .gz generados por logging_engine.py, lee cada
linea como JSON, y certifica que la estructura contenga lo que exige
la consigna:
  - Metadatos basicos: timestamp (ISO 8601 UTC), level, logger,
    threadName, taskName.
  - Si el log corresponde a un error: el arbol de excepcion con tipo,
    mensaje y notas, incluyendo (si aplica) sub_exceptions de un
    ExceptionGroup y/o caused_by encadenado.

Uso:
    python forensic_check.py                     # revisa logs/*.gz
    python forensic_check.py --log-dir otra_ruta  # revisa otra carpeta
    python forensic_check.py --verbose            # muestra cada linea

Codigo de salida:
    0 -> todos los archivos .gz encontrados son validos
    1 -> se encontro al menos un problema estructural
    2 -> no se encontro ningun archivo .gz para analizar
"""

from __future__ import annotations

import argparse
import gzip
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path


# Campos que TODO log, sin excepcion, debe tener segun la consigna.
CAMPOS_OBLIGATORIOS = ("timestamp", "level", "logger", "message")

# Campos de metadatos de entorno que la consigna pide explicitamente
# (Integrante 3: "metadatos del entorno de ejecucion").
CAMPOS_METADATOS = ("process", "threadName", "taskName")


@dataclass
class ResultadoArchivo:
    ruta: Path
    lineas_totales: int = 0
    lineas_validas: int = 0
    lineas_con_excepcion: int = 0
    problemas: list[str] = field(default_factory=list)

    @property
    def es_valido(self) -> bool:
        return not self.problemas and self.lineas_totales > 0


def _validar_timestamp_iso8601(valor: str) -> bool:
    """Confirma que el timestamp sea parseable como ISO 8601."""
    try:
        # Python 3.11+ entiende directamente el formato con offset,
        # incluyendo el sufijo 'Z' si estuviera presente.
        from datetime import datetime

        datetime.fromisoformat(valor.replace("Z", "+00:00"))
        return True
    except (ValueError, AttributeError):
        return False


def _validar_arbol_excepcion(exc: dict, numero_linea: int, problemas: list[str]) -> None:
    """
    Verifica recursivamente que un nodo de excepcion tenga la forma
    esperada: type, message, notes, y opcionalmente caused_by /
    sub_exceptions, tal como los arma AsyncJSONFormatter.
    """
    for campo in ("type", "message"):
        if campo not in exc:
            problemas.append(
                f"Linea {numero_linea}: al nodo de excepcion le falta "
                f"el campo obligatorio '{campo}'."
            )

    if "notes" in exc and not isinstance(exc["notes"], list):
        problemas.append(
            f"Linea {numero_linea}: 'notes' deberia ser una lista, "
            f"se encontro {type(exc['notes']).__name__}."
        )

    if "caused_by" in exc:
        _validar_arbol_excepcion(exc["caused_by"], numero_linea, problemas)

    if "sub_exceptions" in exc:
        if not isinstance(exc["sub_exceptions"], list):
            problemas.append(
                f"Linea {numero_linea}: 'sub_exceptions' deberia ser "
                f"una lista."
            )
        else:
            for sub in exc["sub_exceptions"]:
                _validar_arbol_excepcion(sub, numero_linea, problemas)


def _abrir_para_lectura(ruta: Path):
    """
    Abre el archivo en modo texto. Si termina en .gz lo descomprime al
    vuelo; si no (por ejemplo un .log plano todavia no rotado), lo abre
    directamente.
    """
    if ruta.suffix == ".gz":
        return gzip.open(ruta, "rt", encoding="utf-8")
    return open(ruta, "rt", encoding="utf-8")


def analizar_archivo_gz(ruta: Path, verbose: bool = False) -> ResultadoArchivo:
    """
    Descomprime un archivo .gz (o lee un .log plano) y valida cada
    linea JSON que contiene.
    """
    resultado = ResultadoArchivo(ruta=ruta)

    try:
        with _abrir_para_lectura(ruta) as f:
            for numero_linea, linea in enumerate(f, start=1):
                linea = linea.strip()
                if not linea:
                    continue

                resultado.lineas_totales += 1

                if verbose:
                    print(f"  [{ruta.name}:{numero_linea}] {linea[:120]}")

                try:
                    registro = json.loads(linea)
                except json.JSONDecodeError as error:
                    resultado.problemas.append(
                        f"Linea {numero_linea}: no es JSON valido ({error})."
                    )
                    continue

                # Campos obligatorios de cualquier log.
                faltantes = [c for c in CAMPOS_OBLIGATORIOS if c not in registro]
                if faltantes:
                    resultado.problemas.append(
                        f"Linea {numero_linea}: faltan campos obligatorios "
                        f"{faltantes}."
                    )
                    continue

                # Timestamp en formato ISO 8601 UTC.
                if not _validar_timestamp_iso8601(registro["timestamp"]):
                    resultado.problemas.append(
                        f"Linea {numero_linea}: 'timestamp' no tiene "
                        f"formato ISO 8601 valido: {registro['timestamp']!r}."
                    )

                # Metadatos de entorno (pueden faltar algunos segun el
                # contexto de ejecucion, pero se avisa si faltan todos).
                metadatos_presentes = [c for c in CAMPOS_METADATOS if c in registro]
                if not metadatos_presentes:
                    resultado.problemas.append(
                        f"Linea {numero_linea}: no se encontro ningun "
                        f"metadato de entorno {CAMPOS_METADATOS}."
                    )

                # Si el log corresponde a un error, validar el arbol
                # de excepcion.
                if "exception" in registro:
                    resultado.lineas_con_excepcion += 1
                    _validar_arbol_excepcion(
                        registro["exception"], numero_linea, resultado.problemas
                    )

                if not resultado.problemas or resultado.problemas[-1:] == []:
                    resultado.lineas_validas += 1

    except OSError as error:
        resultado.problemas.append(f"No se pudo abrir/descomprimir el archivo: {error}")

    # lineas_validas se recalcula al final para contar bien incluso si
    # una linea posterior agrego problemas retroactivamente.
    resultado.lineas_validas = resultado.lineas_totales - len(
        {p.split(":")[0] for p in resultado.problemas if p.startswith("Linea")}
    )

    return resultado


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Certifica la estructura de los logs .gz de TritonMonitor."
    )
    parser.add_argument(
        "--log-dir",
        default="logs",
        help="Carpeta donde buscar archivos .gz (default: logs/).",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Muestra cada linea analizada.",
    )
    parser.add_argument(
        "--incluir-log-plano",
        action="store_true",
        help="Ademas de los .gz, certifica tambien el .log sin comprimir todavia.",
    )
    args = parser.parse_args()

    carpeta = Path(args.log_dir)
    archivos = sorted(carpeta.glob("*.gz"))

    if args.incluir_log_plano:
        archivos += sorted(carpeta.glob("*.log"))

    if not archivos:
        print(f"[AVISO] No se encontro ningun archivo .gz en '{carpeta}'.")
        print(
            "        Esto es normal si el log todavia no rotó "
            "(el limite es 2 MB). Usá --incluir-log-plano para "
            "certificar el .log actual sin esperar a la rotación."
        )
        return 2

    print(f"Analizando {len(archivos)} archivo(s) en '{carpeta}'...\n")

    algun_problema = False
    for ruta in archivos:
        resultado = analizar_archivo_gz(ruta, verbose=args.verbose)

        estado = "OK" if resultado.es_valido else "CON PROBLEMAS"
        print(f"[{estado}] {resultado.ruta.name}")
        print(f"    Lineas totales: {resultado.lineas_totales}")
        print(f"    Lineas con arbol de excepcion: {resultado.lineas_con_excepcion}")

        if resultado.problemas:
            algun_problema = True
            print(f"    Problemas encontrados ({len(resultado.problemas)}):")
            for problema in resultado.problemas:
                print(f"      - {problema}")
        print()

    if algun_problema:
        print("Resultado final: se encontraron inconsistencias. Ver detalle arriba.")
        return 1

    print("Resultado final: todos los archivos .gz tienen una estructura valida.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
