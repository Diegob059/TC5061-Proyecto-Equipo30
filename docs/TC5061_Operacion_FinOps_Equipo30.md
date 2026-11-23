---
header-includes:
  - \usepackage{booktabs}
  - \usepackage{fancyhdr}
  - \pagestyle{fancy}
  - \fancyhead[L]{\small\color{gray} TC5061 — Operaciones de Inteligencia Artificial (MLOps)}
  - \fancyhead[R]{\small\color{gray} Equipo 30 | Microservicios, CI/CD y FinOps}
  - \fancyfoot[C]{\small\thepage}
  - \setlength{\parskip}{4pt}
---

# TC5061 — Plataforma MiBici MLOps: Orquestación, CI/CD, Pruebas de Carga y FinOps

**Institución:** Tecnológico de Monterrey — Maestría en Inteligencia Artificial Aplicada  
**Curso:** TC5061 Operaciones de Inteligencia Artificial (Entregable 7 / Actividad 9)  
**Equipo 30:** Ricardo Bahamón (A01840023), Diego Becerril (A01748115), Gregorio Escobedo (A01840612), Freddin Alcantara (A01797741)  
**Fecha:** 22 de noviembre de 2026 | **Repositorio:** https://github.com/Diegob059/TC5061-Proyecto-Equipo30

---

## 1. Resumen Ejecutivo y Arquitectura Operable con Docker Compose

Este entregable consolida el microservicio de predicción de riesgo operativo para las **470 estaciones de MiBici Guadalajara** (Pregunta 2: clasificación multiclase Normal / Desabasto / Saturación a horizonte de 2 horas con LightGBM) como un sistema operable de punta a punta: orquestado con un solo comando mediante **Docker Compose**, verificado de forma continua en **GitHub Actions**, estresado bajo carga real con **Locust** y **docker stats**, y costeado mediante **FinOps**.

El archivo `docker-compose.yml` orquesta dos servicios acoplados sobre una red privada `mibici_net` (`driver: bridge`): (1) **`mlflow`** (servidor de tracking y Model Registry respaldado por SQLite y volumen persistente `mlflow_data`) y (2) **`api`** (FastAPI + Uvicorn + LightGBM sobre `python:3.12-slim` y `libgomp1`), el cual consume el alias `models:/mibici-equipo30-p2-riesgo@champion` vía `http://mlflow:5000`. Se incorporaron configuraciones avanzadas de producción: `depends_on` con `condition: service_healthy`, `healthcheck` HTTP en ambos servicios, límites de cómputo y memoria parametrizables vía `.env.example` (`1.0 vCPU` y `1024 MiB` por contenedor) y políticas de reinicio (`unless-stopped` / `on-failure`). Con un solo comando (`docker compose up -d --build`), ambos contenedores arrancan en estado `healthy` y aprueban **10/10 comprobaciones** de contrato HTTP e inspección de contenedor (`scripts/verify_container_api.py`).

## 2. Pipeline de CI/CD Automatizado en GitHub Actions

Se implementó el flujo `.github/workflows/ci-cd.yml` disparado automáticamente en cada `push` y `pull_request` hacia `main` (con `concurrency` para cancelar ejecuciones obsoletas). Su diseño consta de tres etapas encadenadas:

1. **Matriz de Pruebas (`test-suite`):** Ejecuta en paralelo dos suites (`api-and-ops` y `pipelines-and-validation`) sobre Python 3.12 con caché de dependencias `pip` (`actions/setup-python@v5`), cubriendo pruebas unitarias de API, contrato Pydantic, Locust, FinOps, DeepChecks, Evidently, A/B testing y reproducibilidad, publicando reportes JUnit como artefactos.
2. **Construcción, Compose E2E y Humo de Carga (`build-and-validate-compose`):** Valida `docker compose config`, construye la imagen OCI con Docker Buildx y caché de capas GHA (`type=gha`), levanta el servicio `mlflow`, siembra un modelo LightGBM firmado bajo `@champion` (`scripts/seed_ci_model.py`), arranca la API con `docker compose up -d`, ejecuta los 10 casos de `verify_container_api.py` y corre una prueba de humo headless de Locust capturando `docker stats` en el resumen del workflow (`$GITHUB_STEP_SUMMARY`).
3. **Publicación Continua (`publish-image`):** Al fusionar a `main`, construye y publica automáticamente la imagen etiquetada (`latest` y `sha-<commit>`) en GitHub Container Registry (`ghcr.io`). Verificado en verde sobre main en GitHub Actions (Run ID 45089041084: pruebas en matriz, Compose E2E, Locust y publicación en GHCR).

## 3. Pruebas de Carga con Locust y Monitoreo de Recursos (`docker stats`)

Para evaluar el comportamiento real bajo carga, `load_tests/locustfile.py` simula despachadores del Centro de Control Operativo (CCO) y sondeos de telemetría con perfiles realistas del AMG (35% pico matutino de desabasto, 35% pico vespertino de saturación, 30% valle normal; ponderación 10:1:1 entre `POST /predict`, `GET /health` y `GET /model-info`). Se ejecutaron tres escenarios escalonados contra el contenedor Docker de la API registrando simultáneamente `docker stats --no-stream` cada segundo (`scripts/run_load_and_monitor.py`):

| Escenario | Peticiones | RPS Total | Lat. Media (ms) | p50 (ms) | p95 (ms) | p99 (ms) | Error % | API CPU Med/Pico | API RAM Pico (MiB) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | :---: | ---: |
| Carga Baja (10 usuarios) | 914 | 31.5 | 8.1 | 7 | 17 | 24 | 0.00% | 15.8% / 24.0% | 171.6 |
| Carga Media (50 usuarios) | 6,873 | 156.0 | 6.8 | 5 | 17 | 38 | 0.00% | 40.1% / 50.5% | 170.9 |
| Carga Alta / Estrés (100 usuarios) | 13,555 | 307.5 | 13.5 | 9 | 42 | 73 | 0.00% | 70.3% / 79.6% | 173.1 |

![](reports/figures/semana10_locust_performance.png){width=86%}

**Interpretación del Desempeño:** El microservicio mantuvo **0.00% de tasa de error** a lo largo de los tres niveles de concurrencia. En carga baja (10 usuarios), la API responde con latencia mediana de **7 ms** (p95 de **17 ms**) a **31.5 RPS**. Al escalar a 50 y 100 usuarios concurrentes, el throughput alcanza **307.5 RPS** mientras la latencia p95 crece hasta **42 ms** (p99 **73 ms**). Esto evidencia que el límite de concurrencia de un único proceso Uvicorn (`1.0 vCPU` asignado) radica en la **saturación de CPU** (pico de **79.6%**) durante la inferencia síncrona de LightGBM y el armado de DataFrames `pandas`, y no en agotamiento de memoria.

![](reports/figures/semana10_locust_timeseries.png){width=84%}

**Monitoreo de Contenedores (`docker stats`):** La huella de memoria RAM del contenedor `api` se mantuvo notablemente baja y estable en **173.1 MiB** (<20% del límite de `1024 MiB`), sin indicios de fugas de memoria (*memory leaks*) bajo estrés. Por su parte, el contenedor `mlflow` consumió **734.5 MiB** de RAM pero menos de 2% de CPU durante la inferencia, confirmando que una vez cargado `@champion` en memoria al arrancar la API, el tráfico de predicción queda completamente desacoplado del Model Registry.

![](reports/figures/semana10_docker_stats.png){width=86%}

## 4. Análisis FinOps: Costo por Inferencia y Propuestas de Optimización

Con la telemetría observada —capacidad sostenida de **307.5 RPS** (equivalente a **808,136,280 inferencias/mes** por réplica al 100% de saturación), latencia nominal de **6.8 ms** y consumo pico de **173.1 MiB** de RAM— se modeló el costo operativo mensual y unitario en nube pública (tarifas públicas AWS `us-east-1` y GCP `us-central1`). Dado que MiBici opera 19 horas diarias (05:00–00:00, ~577.6 h/mes) sobre 470 estaciones, se evaluaron dos cargas reales: **Monitoreo CCO Estándar** (1 predicción/estación cada 5 min = **3.26M inferencias/mes**) y **Tiempo Real** (1 predicción/estación cada 1 min = **16.29M inferencias/mes**):

| Topología de Despliegue en Nube | Rép. | USD/mes (16.3M) | USD/1M inf (16.3M) | USD/inferencia (16.3M) | USD/1M inf (3.26M) |
| :--- | :---: | ---: | ---: | ---: | ---: |
| AWS ECS Fargate x86_64 (1 vCPU, 2 GB — 24/7 sin optimizar) | 1 | $36.04 | $2.21 | $0.00000221 | $11.06 |
| AWS ECS Fargate ARM64 Graviton (0.5 vCPU, 1 GB — 24/7 Right-sized) | 1 | $14.42 | $0.89 | $0.00000089 | $4.43 |
| AWS ECS Fargate ARM64 (0.5 vCPU, 1 GB — Auto-stop nocturno 19h/día) | 1 | $11.41 | $0.70 | $0.00000070 | $3.50 |
| AWS EC2 c7g.medium ARM64 (1 vCPU, 2 GB — 1-yr Savings Plan) | 1 | $16.64 | $1.02 | $0.00000102 | $5.11 |
| GCP Cloud Run Serverless (1 vCPU, 512 MB — Scale-to-Zero por petición) | 1 | $12.68 | $0.78 | $0.00000078 | $0.78 |

![](reports/figures/semana10_finops_costs.png){width=86%}

**Hallazgos y Optimizaciones FinOps Justificadas con Datos:**

1. **Right-Sizing + Arquitectura ARM64 Graviton (-60.0% inmediato):** Al observar solo **173.1 MiB** de RAM en `docker stats`, reducir la asignación base de `1 vCPU / 2 GB` x86 (`$36.04/mes`) a `0.5 vCPU / 1 GB` ARM64 reduce el costo fijo mensual en 60%, manteniendo más de 4× de margen de memoria y capacidad suficiente para absorber los 7.8 RPS promedio de tiempo real.
2. **Apagado Programado Nocturno (-68.3% total):** Alinear la disponibilidad del servicio al horario operativo real de MiBici (05:00–00:00, apagando la tarea 5 h/noche) baja el costo de tiempo real a **$11.41/mes** (**$0.70 por millón de inferencias**).
3. **Serverless Scale-to-Zero para Frecuencia Estándar (-93.0%):** En el escenario CCO de 5 minutos (3.26M inferencias/mes, ~1.57 RPS promedio), una instancia 24/7 permanece ociosa >95% del tiempo. Migrar a **GCP Cloud Run** elimina el *idle cost* y reduce el gasto a **$2.54/mes** (**$0.78/1M inferencias**), mientras que para 16.3M/mes (**$12.68/mes**) conviene ya Fargate ARM64 programado.
4. **Desacoplamiento de MLflow y Batching Vectorizado:** Evitar escalar el servidor MLflow (734 MiB) junto con la API —sirviendo el artefacto `@champion` desde almacenamiento objeto (S3/GCS) al arranque— ahorra ~$15–$25 USD/mes adicionales. Asimismo, habilitar un endpoint `POST /predict-batch` que evalúe las 470 estaciones en un único arreglo NumPy (eliminando 469 ciclos de serialización HTTP/pandas) reduciría la CPU por inferencia en >70% y bajaría la latencia total de barrido de ~5 s a <25 ms.

## 5. Conclusiones y Trabajo Colaborativo

La plataforma MiBici del Equipo 30 queda consolidada como un sistema MLOps de grado operativo: reproducible en un solo comando (`docker compose up -d --build`), blindado por un pipeline CI/CD en verde en GitHub Actions, caracterizado empíricamente hasta 100 usuarios concurrentes con 0% de errores y optimizado financieramente con ahorros documentados de hasta **68.3%–93.0%** respecto a un despliegue ingenuo 24/7. La documentación en `README.md` se actualizó con los comandos de operación, CI/CD, Locust y FinOps, manteniendo la trazabilidad colaborativa mediante ramas temáticas y Pull Requests en GitHub Flow.
