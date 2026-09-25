"""
Prueba:
  1. Los validadores de sanitizer.py (Integrante 1) rechazan entradas
     invalidas y aceptan las validas.
  2. core.py (Integrante 2) lanza correctamente ProviderTimeoutError
     cuando se le da un timeout demasiado agresivo (inyeccion de caos
     real, contra los endpoints de JSONPlaceholder por internet).
  3. El sistema no se rompe con un traceback crudo ante esas
     condiciones limite: el error queda prolijamente encapsulado en
     las excepciones propias de exceptions.py.

Nota: las pruebas que llaman a monitorear_clusters() hacen peticiones HTTP reales. 
Si no hay conexion a internet, esas pruebas especificas van a fallar por un motivo distinto al que evaluan (no van a ser "falsos positivos" del codigo, sino falta de red en el entorno de ejecucion).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pytest
import subprocess

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from triton_telemetry.core import monitorear_clusters

from triton_telemetry.exceptions import (
    NetworkPeeringError,
    ProviderTimeoutError,
)
from triton_telemetry.sanitizer import validar_cluster_id, validar_timeout

class TestValidarTimeout:
    #prueba 1, recordemos que el rango es de 0,1 a 5 segundos
    def test_timeout_valido_dentro_del_rango(self):
        assert validar_timeout("3.0") == 3.0

    def test_timeout_valido_cerca_del_limite_inferior(self):
        # Prueba 2: 0.1 es el limite EXCLUIDO, 0.11 debe ser valido.
        assert validar_timeout("0.11") == pytest.approx(0.11)

    def test_timeout_rechaza_el_limite_inferior_exacto(self):
        with pytest.raises(argparse.ArgumentTypeError):
            validar_timeout("0.1")
    # el 5 no está incluido dentro del rango
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
            "cluster-us-east-1", 
            "us-east-01",
            "",
        ],
    )
    def test_cluster_id_invalido(self, cluster_id):
        with pytest.raises(argparse.ArgumentTypeError):
            validar_cluster_id(cluster_id)

class TestInyeccionDeCaos:

    @pytest.mark.asyncio
    async def test_timeout_agresivo_lanza_exception_group_con_provider_timeout(self):
  
        with pytest.raises(ExceptionGroup) as exc_info:
            await monitorear_clusters(0.001)

        grupo = exc_info.value
        timeouts, resto = grupo.split(ProviderTimeoutError)
        assert timeouts is not None, (
        )

    @pytest.mark.asyncio
    async def test_timeout_normal_no_lanza_excepciones(self):
        resultados = await monitorear_clusters(5.0)
        assert len(resultados) == 3
        for resultado in resultados:
            assert resultado["status"] == "OK"

class TestEncapsulamientoDeErrores:
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

#Llamadas Concurrentes masivas a la CLI

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pytest

import subprocess

class TestEjecucionCLIMasiva:

    def test_ejecucion_masiva_cli_con_modo_caos(self):
        # Ruta al script principal
        app_path = Path(__file__).resolve().parents[1] / "app_operator.py"
        
        comando = [
            sys.executable,
            str(app_path),
            "--cluster", "cluster-us-east-01",
            "--timeout", "0.1",
            "--chaos"
        ]

        # Lanza 3 procesos simultáneos de la CLI
        procesos = [
            subprocess.Popen(comando, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            for _ in range(3)
        ]

        for proc in procesos:
            stdout, stderr = proc.communicate()
            assert proc.returncode in (0, 1), f"La CLI colapsó inesperadamente con código {proc.returncode}"

# Permite ejecutar pytest desde cualquier carpeta, encontrando el
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from triton_telemetry.core import monitorear_clusters
#Recordemos que monitorar_cluster se encarga de consultar en paralelos los 3 servidores y su alguno
# falla, agrupa todos los errores
from triton_telemetry.exceptions import (
    NetworkPeeringError,
    ProviderTimeoutError,
)
from triton_telemetry.sanitizer import validar_cluster_id, validar_timeout



class TestValidarTimeout:
    def test_timeout_valido_dentro_del_rango(self):
        assert validar_timeout("3.0") == 3.0

    def test_timeout_valido_cerca_del_limite_inferior(self):
        assert validar_timeout("0.11") == pytest.approx(0.11)

    def test_timeout_rechaza_el_limite_inferior_exacto(self):
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
            "cluster-us-east-1",  
            "us-east-01",
            "",
        ],
    )
    def test_cluster_id_invalido(self, cluster_id):
        with pytest.raises(argparse.ArgumentTypeError):
            validar_cluster_id(cluster_id)


class TestInyeccionDeCaos:

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
        )

    @pytest.mark.asyncio
    async def test_timeout_normal_no_lanza_excepciones(self):
        resultados = await monitorear_clusters(5.0)
        assert len(resultados) == 3
        for resultado in resultados:
            assert resultado["status"] == "OK"


class TestEncapsulamientoDeErrores:
  
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
# Llamadas concurrentes masivas
class TestEjecucionCLIMasiva:

    def test_ejecucion_masiva_cli_con_modo_caos(self):
        app_path = Path(__file__).resolve().parents[1] / "app_operator.py"
        
        comando = [
            sys.executable,
            str(app_path),
            "--cluster", "cluster-us-east-01",
            "--timeout", "0.1",
            "--chaos"
        ]

        # Lanza 3 procesos simultáneos de la CLI
        procesos = [
            subprocess.Popen(comando, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            for _ in range(3)
        ]

        for proc in procesos:
            stdout, stderr = proc.communicate()
            assert proc.returncode in (0, 1), f"La CLI colapsó inesperadamente con código {proc.returncode}"
