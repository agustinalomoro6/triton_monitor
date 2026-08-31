"""
test_chaos.py
--------------
Integrante 6 - Suite de pruebas automatizada (Caos y validacion).

Prueba:
  1. Los validadores de sanitizer.py (Integrante 1) rechazan entradas
     invalidas y aceptan las validas.
  2. core.py (Integrante 2) lanza correctamente ProviderTimeoutError
     cuando se le da un timeout demasiado agresivo (inyeccion de caos
     real, contra los endpoints de JSONPlaceholder por internet).
  3. El sistema no se rompe con un traceback crudo ante esas
     condiciones limite: el error queda prolijamente encapsulado en
     las excepciones propias de exceptions.py.

Como ejecutar (parado en la carpeta raiz del proyecto, triton_monitor):
    pip install pytest --break-system-packages
    pytest src/tests/test_chaos.py -v

Nota: las pruebas que llaman a monitorear_clusters() hacen peticiones
HTTP reales. Si no hay conexion a internet, esas pruebas especificas
van a fallar por un motivo distinto al que evaluan (no van a ser
"falsos positivos" del codigo, sino falta de red en el entorno de
ejecucion).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pytest

# Permite ejecutar pytest desde cualquier carpeta, encontrando el
# paquete triton_telemetry (ubicado en src/).
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from triton_telemetry.core import monitorear_clusters
from triton_telemetry.exceptions import (
    NetworkPeeringError,
    ProviderTimeoutError,
)
from triton_telemetry.sanitizer import validar_cluster_id, validar_timeout


# =====================================================================
# Grupo 1 - Validadores de frontera (sanitizer.py, Integrante 1)
# =====================================================================

class TestValidarTimeout:
    """Prueba los limites exactos del validador de --timeout."""

    def test_timeout_valido_dentro_del_rango(self):
        assert validar_timeout("3.0") == 3.0

    def test_timeout_valido_cerca_del_limite_inferior(self):
        # 0.1 es el limite EXCLUIDO, 0.11 debe ser valido.
        assert validar_timeout("0.11") == pytest.approx(0.11)

    def test_timeout_rechaza_el_limite_inferior_exacto(self):
        # La consigna pide "estrictamente" entre 0.1 y 5.0.
        with pytest.raises(argparse.ArgumentTypeError):
            validar_timeout("0.1")

    def test_timeout_rechaza_el_limite_superior_exacto(self):
        with pytest.raises(argparse.ArgumentTypeError):
            validar_timeout("5.0")

    def test_timeout_rechaza_valor_fuera_de_rango(self):
        with pytest.raises(argparse.ArgumentTypeError):
            validar_timeout("99")

    def test_timeout_rechaza_texto_no_numerico(self):
        with pytest.raises(argparse.ArgumentTypeError):
            validar_timeout("abc")


class TestValidarClusterId:
    """Prueba el formato cluster-<region>-<numero> con regex."""

    @pytest.mark.parametrize(
        "cluster_id",
        ["cluster-us-east-01", "cluster-sa-east-99", "cluster-eu-west-10"],
    )
    def test_cluster_id_valido(self, cluster_id):
        assert validar_cluster_id(cluster_id) == cluster_id

    @pytest.mark.parametrize(
        "cluster_id",
        [
            "CLUSTER_MAL",
            "cluster-us-1",
            "cluster-us-east-1",  # un solo digito, se exige 2 o mas
            "us-east-01",
            "",
        ],
    )
    def test_cluster_id_invalido(self, cluster_id):
        with pytest.raises(argparse.ArgumentTypeError):
            validar_cluster_id(cluster_id)


# =====================================================================
# Grupo 2 - Inyeccion de caos real contra core.py (Integrante 2)
# =====================================================================

class TestInyeccionDeCaos:
    """
    Fuerza condiciones limite reales de red para confirmar que
    core.py traduce correctamente los fallos de httpx a las
    excepciones semanticas propias, en vez de dejar pasar un
    traceback crudo de la libreria de terceros.
    """

    @pytest.mark.asyncio
    async def test_timeout_agresivo_lanza_exception_group_con_provider_timeout(self):
        """
        Con un timeout extremadamente bajo (0.001s), es practicamente
        imposible que un servidor real responda a tiempo. Se espera
        que TaskGroup agrupe los fallos y que, dentro del grupo,
        aparezca al menos un ProviderTimeoutError.
        """
        with pytest.raises(ExceptionGroup) as exc_info:
            await monitorear_clusters(0.001)

        grupo = exc_info.value
        timeouts, resto = grupo.split(ProviderTimeoutError)
        assert timeouts is not None, (
            "Se esperaba al menos un ProviderTimeoutError dentro del "
            "ExceptionGroup ante un timeout de 0.001s."
        )

    @pytest.mark.asyncio
    async def test_timeout_normal_no_lanza_excepciones(self):
        """
        Caso de control (Escenario A): con un timeout razonable, los
        3 proveedores deberian responder sin lanzar ningun error.
        """
        resultados = await monitorear_clusters(5.0)
        assert len(resultados) == 3
        for resultado in resultados:
            assert resultado["status"] == "OK"


# =====================================================================
# Grupo 3 - El sistema nunca deja pasar excepciones "crudas"
# =====================================================================

class TestEncapsulamientoDeErrores:
    """
    Verifica que, ante un fallo de red, NUNCA se propague una
    excepcion cruda de httpx hacia afuera de core.py: siempre debe
    salir envuelta en una excepcion propia de exceptions.py.
    """

    @pytest.mark.asyncio
    async def test_no_se_filtran_excepciones_de_httpx_sin_traducir(self):
        import httpx

        with pytest.raises(ExceptionGroup) as exc_info:
            await monitorear_clusters(0.001)

        grupo = exc_info.value
        for sub_exc in grupo.exceptions:
            assert not isinstance(sub_exc, httpx.HTTPError), (
                f"Se filtro una excepcion cruda de httpx sin traducir: "
                f"{type(sub_exc).__name__}"
            )
