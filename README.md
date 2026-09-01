# TritonMonitor

Herramienta de consola (CLI) en Python moderno (3.11+) para consultar el
estado de clústeres multicloud (AWS, Azure, GCP) mediante peticiones HTTP
asíncronas reales, tolerar fallos concurrentes de red y persistir logs
estructurados en JSON comprimido sin bloquear el bucle de eventos.

## Objetivo

El sistema:

1. Consulta APIs reales en paralelo con `httpx`, simulando el monitoreo
   de AWS, Azure y GCP.
2. Gestiona errores concurrentes agrupándolos en un `ExceptionGroup` y
   capturándolos con la sintaxis moderna `except*`.
3. Envía los logs a una cola en memoria (`queue.Queue`) para que un
   hilo en segundo plano (`QueueListener`) los formatee a JSON
   estructurado y los guarde en archivos rotativos comprimidos `.gz`.
4. Valida estrictamente los argumentos de entrada con `argparse`.

## Estructura del proyecto

```
triton_monitor/
├── src/
│   ├── triton_telemetry/
│   │   ├── __init__.py          # Exporta la API pública (__all__)
│   │   ├── exceptions.py        # Jerarquía de excepciones semánticas
│   │   ├── sanitizer.py         # Validadores personalizados para argparse
│   │   ├── core.py              # Lógica asíncrona de red (asyncio + httpx)
│   │   └── logging_engine.py    # Formateador JSON y pipeline de logging
│   ├── app_operator.py          # Punto de entrada ejecutable (CLI + except*)
│   └── tests/
│       └── test_chaos.py        # Suite de pruebas (validadores + caos real)
├── forensic_check.py            # Certifica la estructura de los logs .gz
├── requirements.txt
└── README.md
```

## Arquitectura

```mermaid
flowchart TD
    A["Usuario ejecuta la CLI\ntriton_monitor --cluster ... --timeout ..."] --> B

    subgraph Frontera["Frontera de entrada (sanitizer.py)"]
        B["argparse + validadores\nvalidar_timeout / validar_cluster_id"]
    end

    B -- "argumentos inválidos" --> B1["ArgumentTypeError\nexit code 2"]
    B -- "argumentos válidos" --> C

    subgraph Async["Núcleo asíncrono (core.py)"]
        C["asyncio.TaskGroup()"]
        C --> C1["Consulta AWS\n(httpx.AsyncClient)"]
        C --> C2["Consulta Azure\n(httpx.AsyncClient)"]
        C --> C3["Consulta GCP\n(httpx.AsyncClient)"]
    end

    C1 -- "timeout" --> E1["ProviderTimeoutError\n(+ add_note)"]
    C2 -- "HTTP 504/422" --> E2["CorruptedPayloadError"]
    C3 -- "sin red / DNS" --> E3["NetworkPeeringError"]

    C1 -- "200 OK" --> D["Resultados agregados"]
    C2 -- "200 OK" --> D
    C3 -- "200 OK" --> D

    E1 --> F["ExceptionGroup"]
    E2 --> F
    E3 --> F

    F --> G["app_operator.py\nexcept* ProviderTimeoutError\nexcept* CorruptedPayloadError\nexcept* NetworkPeeringError"]
    D --> H["logger.info(...)"]
    G --> H

    subgraph Logging["Pipeline de logging no bloqueante (logging_engine.py)"]
        H --> I["QueueHandler\n(en el event loop)"]
        I --> J["queue.Queue\n(buzón en memoria)"]
        J --> K["QueueListener\n(hilo secundario)"]
        K --> L["AsyncJSONFormatter\n(JSON + árbol de excepciones)"]
        L --> M["RotatingFileHandler\n(2 MB / 3 backups)"]
        M --> N["Compresión .gz\n(gzip, namer + rotator)"]
    end

    G --> Z["sys.exit(codigo_salida)"]
```

## Instalación

```bash
python -m venv .venv
.venv\Scripts\activate      # En Windows
source .venv/bin/activate   # En Linux/Mac
pip install -r requirements.txt
```

## Uso

```bash
python src/app_operator.py --cluster cluster-us-east-01 --timeout 3.0
```

### Argumentos

| Argumento     | Descripción                                                             | Obligatorio |
|---------------|--------------------------------------------------------------------------|:-----------:|
| `--cluster`   | ID del clúster. Formato `cluster-<region>-<numero>` (ej: `cluster-us-east-01`). | Sí |
| `--timeout`   | Timeout de red en segundos, estrictamente entre 0.1 y 5.0.               | Sí |
| `--log-path`  | Ruta del archivo de log rotativo (default: `logs/triton_monitor.log`).   | No |
| `--debug`     | Modo debug: logging detallado (nivel `DEBUG`). Excluyente con `--emergency`. | No |
| `--emergency` | Modo emergencia: solo errores críticos (nivel `ERROR`). Excluyente con `--debug`. | No |

## Escenarios de prueba

| Escenario | Ejemplo de entrada | Comportamiento esperado |
|-----------|---------------------|--------------------------|
| **A — Operación nominal** | `--cluster cluster-us-east-01 --timeout 3.0` | Los 3 proveedores responden `200 OK` y el sistema termina con éxito. |
| **B — Validación temprana CLI** | `--timeout 99` o un cluster ID mal escrito | El validador frena la ejecución al instante y sale con código de error **2**. |
| **C — Inyección de caos** | `--timeout 0.1` | Ocurren fallos concurrentes, se agrupan en `ExceptionGroup`, se capturan con `except*` y se guardan en el log comprimido `.gz`. |

## Tests

```bash
pip install pytest pytest-asyncio --break-system-packages
pytest src/tests/test_chaos.py -v
```

## Certificación forense de logs

Descomprime y valida la estructura de los archivos `.gz` generados
(timestamp ISO 8601, metadatos de entorno y árbol de excepciones):

```bash
python forensic_check.py --log-dir logs
```
