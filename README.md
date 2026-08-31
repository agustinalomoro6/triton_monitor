\# TritonMonitor



Herramienta de consola (CLI) en Python moderno (3.11+) para consultar el

estado de clusters multicloud (AWS, Azure, GCP) mediante peticiones HTTP

asincronas reales, tolerar fallos concurrentes de red y persistir logs

estructurados en JSON comprimido sin bloquear el bucle de eventos.



\## Objetivo



El sistema:



1\. Consulta APIs reales en paralelo con httpx, simulando el monitoreo

&#x20;  de AWS, Azure y GCP.

2\. Gestiona errores concurrentes agrupandolos en un ExceptionGroup y

&#x20;  capturandolos con la sintaxis moderna except\*.

3\. Envia los logs a una cola en memoria (queue.Queue) para que un

&#x20;  hilo en segundo plano (QueueListener) los formatee a JSON

&#x20;  estructurado y los guarde en archivos rotativos comprimidos .gz.

4\. Valida estrictamente los argumentos de entrada con argparse.



\## Estructura del proyecto



triton\_monitor/

├── src/

│   ├── triton\_telemetry/

│   │   ├── \_\_init\_\_.py

│   │   ├── exceptions.py       # Jerarquia de excepciones semanticas

│   │   ├── sanitizer.py        # Validadores personalizados para argparse

│   │   ├── core.py             # Logica asincrona de red (asyncio + httpx)

│   │   └── logging\_engine.py   # Formateador JSON y pipeline de logging

│   └── app\_operator.py         # Punto de entrada ejecutable (CLI + except\*)

├── requirements.txt

└── README.md



\## Instalacion



python -m venv .venv

.venv\\Scripts\\activate      # En Windows

pip install -r requirements.txt



\## Uso



python src/app\_operator.py --cluster cluster-us-east-01 --timeout 3.0



\### Argumentos



| Argumento      | Descripcion                                                        | Obligatorio |

|----------------|---------------------------------------------------------------------|-------------|

| --cluster      | ID del cluster. Formato cluster-<region>-<numero> (ej: cluster-us-east-01). | Si |

| --timeout      | Timeout de red en segundos, estrictamente entre 0.1 y 5.0.          | Si |

| --log-path     | Ruta del archivo de log rotativo (default: logs/triton\_monitor.log). | No |

| --debug        | Modo debug: logging detallado

