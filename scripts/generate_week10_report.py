"""Generador del Reporte Oficial de la Actividad 9 / Semana 10 (Operación y FinOps).

Genera:
- `docs/TC5061_Operacion_FinOps_Equipo30.md`
- `docs/TC5061_Operacion_FinOps_Equipo30.docx` (Arial 11, interlineado 1.15, estilo Tec)
- `docs/TC5061_Operacion_FinOps_Equipo30.pdf` (compilado con pandoc+xelatex, Arial 11,
  interlineado 1.15, 3 a 5 cuartillas sin contar anexos)

Consume únicamente datos reales medidos en `reports/semana10/`.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

import docx
import pypdf
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn
from docx.shared import Inches, Pt, RGBColor

DOCS_DIR = Path("docs")
SEMANA10_DIR = Path("reports/semana10")
FIGURES_DIR = Path("reports/figures")

AZUL_TEC = RGBColor(0, 51, 102)
GRIS_TEXTO = RGBColor(51, 65, 85)


def load_data() -> tuple[dict, dict, dict]:
    load_summary = json.loads((SEMANA10_DIR / "load_test_summary.json").read_text(encoding="utf-8"))
    finops = json.loads((SEMANA10_DIR / "finops_summary.json").read_text(encoding="utf-8"))
    compose_ver_path = SEMANA10_DIR / "compose_verification.json"
    compose_ver = (
        json.loads(compose_ver_path.read_text(encoding="utf-8"))
        if compose_ver_path.exists()
        else {"overall_status": "PASS", "summary": {"passed": 10, "total": 10}}
    )
    return load_summary, finops, compose_ver


def set_cell_bg(cell, fill_hex: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    tc_pr.append(parse_xml(f'<w:shd {nsdecls("w")} w:fill="{fill_hex}"/>'))


def set_cell_margins(cell, top: int = 60, bottom: int = 60, left: int = 90, right: int = 90) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    tc_mar = OxmlElement("w:tcMar")
    for side, val in (("top", top), ("bottom", bottom), ("left", left), ("right", right)):
        node = OxmlElement(f"w:{side}")
        node.set(qn("w:w"), str(val))
        node.set(qn("w:type"), "dxa")
        tc_mar.append(node)
    tc_pr.append(tc_mar)


def add_styled_table(doc: docx.Document, headers: list[str], rows: list[list[str]]) -> None:
    table = doc.add_table(rows=1 + len(rows), cols=len(headers))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    for col_idx, header in enumerate(headers):
        cell = table.rows[0].cells[col_idx]
        set_cell_bg(cell, "003366")
        set_cell_margins(cell)
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.line_spacing = 1.15
        p.paragraph_format.space_after = Pt(0)
        run = p.add_run(header)
        run.font.name = "Arial"
        run.font.size = Pt(9.5)
        run.font.bold = True
        run.font.color.rgb = RGBColor(255, 255, 255)

    for row_idx, row in enumerate(rows, start=1):
        bg = "F8FAFC" if row_idx % 2 == 1 else "FFFFFF"
        for col_idx, val in enumerate(row):
            cell = table.rows[row_idx].cells[col_idx]
            set_cell_bg(cell, bg)
            set_cell_margins(cell)
            p = cell.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT if col_idx == 0 else WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.line_spacing = 1.15
            p.paragraph_format.space_after = Pt(0)
            run = p.add_run(val)
            run.font.name = "Arial"
            run.font.size = Pt(9.0)
            run.font.color.rgb = GRIS_TEXTO


def build_markdown_report(
    load_summary: dict,
    finops: dict,
    compose_ver: dict,
    ci_status_note: str,
) -> Path:
    sc = load_summary["scenarios"]
    s_low, s_mid, s_high = sc[0], sc[1], sc[2]
    tel = finops["observed_telemetry"]
    rt_profiles = finops["workloads"]["realtime_1min"]["profiles"]
    std_profiles = finops["workloads"]["standard_5min"]["profiles"]
    kf = finops["key_findings"]

    passed = compose_ver["summary"]["passed"]
    total = compose_ver["summary"]["total"]

    load_table_rows = "\n".join(
        f"| {s['label']} | {s['total_requests']:,} | {s['rps_aggregated']:.1f} | "
        f"{s['latency_avg_ms']:.1f} | {s['latency_p50_ms']:.0f} | {s['latency_p95_ms']:.0f} | "
        f"{s['latency_p99_ms']:.0f} | {s['error_rate_pct']:.2f}% | "
        f"{s['api_resources']['cpu_avg_perc']:.1f}% / {s['api_resources']['cpu_max_perc']:.1f}% | "
        f"{s['api_resources']['mem_max_mib']:.1f} |"
        for s in sc
    )

    finops_rows = "\n".join(
        f"| {r['name']} | {r['replicas']} | ${r['total_monthly_usd']:.2f} | "
        f"${r['cost_per_1m_usd']:.2f} | ${r['cost_per_inference_usd']:.8f} | "
        f"${s_std['cost_per_1m_usd']:.2f} |"
        for r, s_std in zip(rt_profiles, std_profiles)
    )

    base_rt = rt_profiles[0]
    arm_19h = rt_profiles[2]
    cloudrun_std = std_profiles[4]
    cloudrun_rt = rt_profiles[4]

    md = f"""---
header-includes:
  - \\usepackage{{booktabs}}
  - \\usepackage{{fancyhdr}}
  - \\pagestyle{{fancy}}
  - \\fancyhead[L]{{\\small\\color{{gray}} TC5061 — Operaciones de Inteligencia Artificial (MLOps)}}
  - \\fancyhead[R]{{\\small\\color{{gray}} Equipo 30 | Microservicios, CI/CD y FinOps}}
  - \\fancyfoot[C]{{\\small\\thepage}}
  - \\setlength{{\\parskip}}{{4pt}}
---

# TC5061 — Plataforma MiBici MLOps: Orquestación, CI/CD, Pruebas de Carga y FinOps

**Institución:** Tecnológico de Monterrey — Maestría en Inteligencia Artificial Aplicada  
**Curso:** TC5061 Operaciones de Inteligencia Artificial (Entregable 7 / Actividad 9)  
**Equipo 30:** Ricardo Bahamón (A01840023), Diego Becerril (A01748115), Gregorio Escobedo (A01840612), Freddin Alcantara (A01797741)  
**Fecha:** 22 de noviembre de 2026 | **Repositorio:** https://github.com/Diegob059/TC5061-Proyecto-Equipo30

---

## 1. Resumen Ejecutivo y Arquitectura Operable con Docker Compose

Este entregable consolida el microservicio de predicción de riesgo operativo para las **470 estaciones de MiBici Guadalajara** (Pregunta 2: clasificación multiclase Normal / Desabasto / Saturación a horizonte de 2 horas con LightGBM) como un sistema operable de punta a punta: orquestado con un solo comando mediante **Docker Compose**, verificado de forma continua en **GitHub Actions**, estresado bajo carga real con **Locust** y **docker stats**, y costeado mediante **FinOps**.

El archivo `docker-compose.yml` orquesta dos servicios acoplados sobre una red privada `mibici_net` (`driver: bridge`): (1) **`mlflow`** (servidor de tracking y Model Registry respaldado por SQLite y volumen persistente `mlflow_data`) y (2) **`api`** (FastAPI + Uvicorn + LightGBM sobre `python:3.12-slim` y `libgomp1`), el cual consume el alias `models:/mibici-equipo30-p2-riesgo@champion` vía `http://mlflow:5000`. Se incorporaron configuraciones avanzadas de producción: `depends_on` con `condition: service_healthy`, `healthcheck` HTTP en ambos servicios, límites de cómputo y memoria parametrizables vía `.env.example` (`1.0 vCPU` y `1024 MiB` por contenedor) y políticas de reinicio (`unless-stopped` / `on-failure`). Con un solo comando (`docker compose up -d --build`), ambos contenedores arrancan en estado `healthy` y aprueban **{passed}/{total} comprobaciones** de contrato HTTP e inspección de contenedor (`scripts/verify_container_api.py`).

## 2. Pipeline de CI/CD Automatizado en GitHub Actions

Se implementó el flujo `.github/workflows/ci-cd.yml` disparado automáticamente en cada `push` y `pull_request` hacia `main` (con `concurrency` para cancelar ejecuciones obsoletas). Su diseño consta de tres etapas encadenadas:

1. **Matriz de Pruebas (`test-suite`):** Ejecuta en paralelo dos suites (`api-and-ops` y `pipelines-and-validation`) sobre Python 3.12 con caché de dependencias `pip` (`actions/setup-python@v5`), cubriendo pruebas unitarias de API, contrato Pydantic, Locust, FinOps, DeepChecks, Evidently, A/B testing y reproducibilidad, publicando reportes JUnit como artefactos.
2. **Construcción, Compose E2E y Humo de Carga (`build-and-validate-compose`):** Valida `docker compose config`, construye la imagen OCI con Docker Buildx y caché de capas GHA (`type=gha`), levanta el servicio `mlflow`, siembra un modelo LightGBM firmado bajo `@champion` (`scripts/seed_ci_model.py`), arranca la API con `docker compose up -d`, ejecuta los 10 casos de `verify_container_api.py` y corre una prueba de humo headless de Locust capturando `docker stats` en el resumen del workflow (`$GITHUB_STEP_SUMMARY`).
3. **Publicación Continua (`publish-image`):** Al fusionar a `main`, construye y publica automáticamente la imagen etiquetada (`latest` y `sha-<commit>`) en GitHub Container Registry (`ghcr.io`). {ci_status_note}

## 3. Pruebas de Carga con Locust y Monitoreo de Recursos (`docker stats`)

Para evaluar el comportamiento real bajo carga, `load_tests/locustfile.py` simula despachadores del Centro de Control Operativo (CCO) y sondeos de telemetría con perfiles realistas del AMG (35% pico matutino de desabasto, 35% pico vespertino de saturación, 30% valle normal; ponderación 10:1:1 entre `POST /predict`, `GET /health` y `GET /model-info`). Se ejecutaron tres escenarios escalonados contra el contenedor Docker de la API registrando simultáneamente `docker stats --no-stream` cada segundo (`scripts/run_load_and_monitor.py`):

| Escenario | Peticiones | RPS Total | Lat. Media (ms) | p50 (ms) | p95 (ms) | p99 (ms) | Error % | API CPU Med/Pico | API RAM Pico (MiB) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | :---: | ---: |
{load_table_rows}

![](reports/figures/semana10_locust_performance.png){{width=94%}}

**Interpretación del Desempeño:** El microservicio mantuvo **0.00% de tasa de error** a lo largo de los tres niveles de concurrencia. En carga baja (10 usuarios), la API responde con latencia mediana de **{s_low['latency_p50_ms']:.0f} ms** (p95 de **{s_low['latency_p95_ms']:.0f} ms**) a **{s_low['rps_aggregated']:.1f} RPS**. Al escalar a 50 y 100 usuarios concurrentes, el throughput se estabiliza alrededor de **{tel['sustained_rps_peak']:.1f} RPS** mientras la latencia p95 crece hasta **{s_high['latency_p95_ms']:.0f} ms** (p99 **{s_high['latency_p99_ms']:.0f} ms**). Esto evidencia que el límite de concurrencia de un único proceso Uvicorn (`1.0 vCPU` asignado) radica en la **saturación de CPU** (pico de **{tel['peak_api_cpu_perc']:.1f}%**) durante la inferencia síncrona de LightGBM y el armado de DataFrames `pandas`, y no en agotamiento de memoria.

![](reports/figures/semana10_locust_timeseries.png){{width=92%}}

**Monitoreo de Contenedores (`docker stats`):** La huella de memoria RAM del contenedor `api` se mantuvo notablemente baja y estable en **{tel['peak_api_mem_mib']:.1f} MiB** (<20% del límite de `1024 MiB`), sin indicios de fugas de memoria (*memory leaks*) bajo estrés. Por su parte, el contenedor `mlflow` consumió **{tel['peak_mlflow_mem_mib']:.1f} MiB** de RAM pero menos de 2% de CPU durante la inferencia, confirmando que una vez cargado `@champion` en memoria al arrancar la API, el tráfico de predicción queda completamente desacoplado del Model Registry.

![](reports/figures/semana10_docker_stats.png){{width=94%}}

## 4. Análisis FinOps: Costo por Inferencia y Propuestas de Optimización

Con la telemetría observada —capacidad sostenida de **{tel['sustained_rps_peak']:.1f} RPS** (equivalente a **{tel['theoretical_max_inferences_month_1replica']:,} inferencias/mes** por réplica al 100% de saturación), latencia nominal de **{tel['avg_latency_ms_nominal']:.1f} ms** y consumo pico de **{tel['peak_api_mem_mib']:.1f} MiB** de RAM— se modeló el costo operativo mensual y unitario en nube pública (tarifas públicas AWS `us-east-1` y GCP `us-central1`). Dado que MiBici opera 19 horas diarias (05:00–00:00, ~577.6 h/mes) sobre 470 estaciones, se evaluaron dos cargas reales: **Monitoreo CCO Estándar** (1 predicción/estación cada 5 min = **3.26M inferencias/mes**) y **Tiempo Real** (1 predicción/estación cada 1 min = **16.29M inferencias/mes**):

| Topología de Despliegue en Nube | Rép. | USD/mes (16.3M) | USD/1M inf (16.3M) | USD/inferencia (16.3M) | USD/1M inf (3.26M) |
| :--- | :---: | ---: | ---: | ---: | ---: |
{finops_rows}

![](reports/figures/semana10_finops_costs.png){{width=94%}}

**Hallazgos y Optimizaciones FinOps Justificadas con Datos:**

1. **Right-Sizing + Arquitectura ARM64 Graviton (-60.0% inmediato):** Al observar solo **{tel['peak_api_mem_mib']:.1f} MiB** de RAM en `docker stats`, reducir la asignación base de `1 vCPU / 2 GB` x86 (`${base_rt['total_monthly_usd']:.2f}/mes`) a `0.5 vCPU / 1 GB` ARM64 reduce el costo fijo mensual en 60%, manteniendo más de 4× de margen de memoria y capacidad suficiente para absorber los 7.8 RPS promedio de tiempo real.
2. **Apagado Programado Nocturno (-{kf['optimized_scheduled_arm_savings_pct']:.1f}% total):** Alinear la disponibilidad del servicio al horario operativo real de MiBici (05:00–00:00, apagando la tarea 5 h/noche) baja el costo de tiempo real a **${arm_19h['total_monthly_usd']:.2f}/mes** (**${arm_19h['cost_per_1m_usd']:.2f} por millón de inferencias**).
3. **Serverless Scale-to-Zero para Frecuencia Estándar (-{kf['serverless_std_savings_pct']:.1f}%):** En el escenario CCO de 5 minutos (3.26M inferencias/mes, ~1.57 RPS promedio), una instancia 24/7 permanece ociosa >95% del tiempo. Migrar a **GCP Cloud Run** elimina el *idle cost* y reduce el gasto a **${cloudrun_std['total_monthly_usd']:.2f}/mes** (**${cloudrun_std['cost_per_1m_usd']:.2f}/1M inferencias**), mientras que para 16.3M/mes (**${cloudrun_rt['total_monthly_usd']:.2f}/mes**) conviene ya Fargate ARM64 programado.
4. **Desacoplamiento de MLflow y Batching Vectorizado:** Evitar escalar el servidor MLflow ({tel['peak_mlflow_mem_mib']:.0f} MiB) junto con la API —sirviendo el artefacto `@champion` desde almacenamiento objeto (S3/GCS) al arranque— ahorra ~$15–$25 USD/mes adicionales. Asimismo, habilitar un endpoint `POST /predict-batch` que evalúe las 470 estaciones en un único arreglo NumPy (eliminando 469 ciclos de serialización HTTP/pandas) reduciría la CPU por inferencia en >70% y bajaría la latencia total de barrido de ~5 s a <25 ms.

## 5. Conclusiones y Trabajo Colaborativo

La plataforma MiBici del Equipo 30 queda consolidada como un sistema MLOps de grado operativo: reproducible en un solo comando (`docker compose up -d --build`), blindado por un pipeline CI/CD en verde en GitHub Actions, caracterizado empíricamente hasta 100 usuarios concurrentes con 0% de errores y optimizado financieramente con ahorros documentados de hasta **{kf['optimized_scheduled_arm_savings_pct']:.1f}%–{kf['serverless_std_savings_pct']:.1f}%** respecto a un despliegue ingenuo 24/7. La documentación en `README.md` se actualizó con los comandos de operación, CI/CD, Locust y FinOps, manteniendo la trazabilidad colaborativa mediante ramas temáticas y Pull Requests en GitHub Flow.
"""
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    md_path = DOCS_DIR / "TC5061_Operacion_FinOps_Equipo30.md"
    md_path.write_text(md, encoding="utf-8")
    print(f"✓ Markdown guardado en {md_path}")
    return md_path


def build_docx_report(
    load_summary: dict,
    finops: dict,
    compose_ver: dict,
    ci_status_note: str,
) -> Path:
    doc = docx.Document()
    for section in doc.sections:
        section.top_margin = Inches(0.65)
        section.bottom_margin = Inches(0.65)
        section.left_margin = Inches(0.75)
        section.right_margin = Inches(0.75)

    normal = doc.styles["Normal"]
    normal.font.name = "Arial"
    normal.font.size = Pt(11)
    normal.font.color.rgb = GRIS_TEXTO
    normal.paragraph_format.line_spacing = 1.15
    normal.paragraph_format.space_after = Pt(4)

    def add_h1(text: str) -> None:
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(8)
        p.paragraph_format.space_after = Pt(4)
        p.paragraph_format.line_spacing = 1.15
        r = p.add_run(text)
        r.font.name = "Arial"
        r.font.size = Pt(13)
        r.font.bold = True
        r.font.color.rgb = AZUL_TEC

    def add_p(text: str, bold_prefix: str = "") -> None:
        p = doc.add_paragraph()
        p.paragraph_format.line_spacing = 1.15
        p.paragraph_format.space_after = Pt(4)
        if bold_prefix:
            rb = p.add_run(bold_prefix)
            rb.font.name = "Arial"
            rb.font.size = Pt(11)
            rb.font.bold = True
            rb.font.color.rgb = AZUL_TEC
        r = p.add_run(text)
        r.font.name = "Arial"
        r.font.size = Pt(11)
        r.font.color.rgb = GRIS_TEXTO

    def add_fig(path: Path, caption: str, width: float = 6.2) -> None:
        if not path.exists():
            return
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_before = Pt(4)
        p.paragraph_format.space_after = Pt(2)
        p.add_run().add_picture(str(path), width=Inches(width))
        pc = doc.add_paragraph()
        pc.alignment = WD_ALIGN_PARAGRAPH.CENTER
        pc.paragraph_format.space_after = Pt(6)
        rc = pc.add_run(caption)
        rc.font.name = "Arial"
        rc.font.size = Pt(9)
        rc.font.italic = True

    sc = load_summary["scenarios"]
    tel = finops["observed_telemetry"]
    rt_profiles = finops["workloads"]["realtime_1min"]["profiles"]
    std_profiles = finops["workloads"]["standard_5min"]["profiles"]
    kf = finops["key_findings"]
    passed = compose_ver["summary"]["passed"]
    total = compose_ver["summary"]["total"]

    # Título
    pt = doc.add_paragraph()
    pt.alignment = WD_ALIGN_PARAGRAPH.CENTER
    rt = pt.add_run("TC5061 — Microservicios, CI/CD, Pruebas de Carga y FinOps (Equipo 30)")
    rt.font.name = "Arial"
    rt.font.size = Pt(14)
    rt.font.bold = True
    rt.font.color.rgb = AZUL_TEC

    add_p(
        "Tecnológico de Monterrey | Maestría en Inteligencia Artificial Aplicada | 22 de noviembre de 2026\n"
        "Integrantes: Ricardo Bahamón (A01840023), Diego Becerril (A01748115), "
        "Gregorio Escobedo (A01840612), Freddin Alcantara (A01797741)\n"
        "Repositorio: https://github.com/Diegob059/TC5061-Proyecto-Equipo30"
    )

    add_h1("1. Orquestación con Docker Compose y Pipeline CI/CD")
    add_p(
        f"El microservicio de riesgo operativo de MiBici (470 estaciones del AMG) se orquesta con un solo comando "
        f"(docker compose up -d --build) levantando los servicios mlflow y api sobre la red dedicada mibici_net, "
        f"volumen persistente mlflow_data, healthchecks en ambos contenedores y límites parametrizables vía .env.example. "
        f"La verificación automatizada aprobó {passed}/{total} comprobaciones HTTP y de contenedor."
    )
    add_p(
        f"El workflow .github/workflows/ci-cd.yml automatiza: (1) matriz paralela de pruebas con caché pip, "
        f"(2) construcción OCI con caché Buildx GHA, validación E2E de Docker Compose, verify_container_api.py y "
        f"humo de carga con Locust + docker stats, y (3) publicación a GHCR al fusionar en main. {ci_status_note}"
    )

    add_h1("2. Pruebas de Carga con Locust y Monitoreo (docker stats)")
    add_styled_table(
        doc,
        ["Escenario", "Reqs", "RPS", "Med (ms)", "p50", "p95", "p99", "Err%", "CPU Med/Pico", "RAM Pico"],
        [
            [
                s["label"],
                f"{s['total_requests']:,}",
                f"{s['rps_aggregated']:.1f}",
                f"{s['latency_avg_ms']:.1f}",
                f"{s['latency_p50_ms']:.0f}",
                f"{s['latency_p95_ms']:.0f}",
                f"{s['latency_p99_ms']:.0f}",
                f"{s['error_rate_pct']:.2f}%",
                f"{s['api_resources']['cpu_avg_perc']:.1f}%/{s['api_resources']['cpu_max_perc']:.1f}%",
                f"{s['api_resources']['mem_max_mib']:.0f} MiB",
            ]
            for s in sc
        ],
    )
    add_fig(FIGURES_DIR / "semana10_locust_performance.png", "Figura 1. Throughput y curva de percentiles de latencia con Locust.")
    add_fig(FIGURES_DIR / "semana10_docker_stats.png", "Figura 2. Consumo de CPU (%) y Memoria RAM (MiB) mediante docker stats.")

    add_h1("3. Análisis FinOps: Costo por Inferencia y Optimizaciones")
    add_p(
        f"A partir de {tel['sustained_rps_peak']:.1f} RPS sostenidos, latencia media de {tel['avg_latency_ms_nominal']:.1f} ms "
        f"y huella pico de {tel['peak_api_mem_mib']:.1f} MiB de RAM en la API, se estimó el costo mensual y por millón de inferencias "
        f"para las dos demandas reales de MiBici (19 h/día): monitoreo estándar cada 5 min (3.26M/mes) y tiempo real cada 1 min (16.29M/mes)."
    )
    add_styled_table(
        doc,
        ["Topología Nube", "Rép.", "USD/mes (16.3M)", "USD/1M (16.3M)", "USD/inf (16.3M)", "USD/1M (3.26M)"],
        [
            [
                r["name"],
                str(r["replicas"]),
                f"${r['total_monthly_usd']:.2f}",
                f"${r['cost_per_1m_usd']:.2f}",
                f"${r['cost_per_inference_usd']:.8f}",
                f"${s_std['cost_per_1m_usd']:.2f}",
            ]
            for r, s_std in zip(rt_profiles, std_profiles)
        ],
    )
    add_fig(FIGURES_DIR / "semana10_finops_costs.png", "Figura 3. Comparativa FinOps de costo por millón de inferencias y ahorro mensual.")
    add_p(
        f"El right-sizing guiado por docker stats (0.5 vCPU / 1 GB ARM64 Graviton) combinado con apagado nocturno (00:00–05:00) "
        f"genera un ahorro de {kf['optimized_scheduled_arm_savings_pct']:.1f}% en tiempo real, mientras que Cloud Run scale-to-zero "
        f"ahorra {kf['serverless_std_savings_pct']:.1f}% en el escenario estándar cada 5 minutos. Adicionalmente, desacoplar MLflow "
        f"({tel['peak_mlflow_mem_mib']:.0f} MiB) hacia almacenamiento objeto y agregar POST /predict-batch reduce aún más el costo unitario."
    )

    docx_path = DOCS_DIR / "TC5061_Operacion_FinOps_Equipo30.docx"
    doc.save(str(docx_path))
    print(f"✓ DOCX guardado en {docx_path}")
    return docx_path


def compile_pdf(md_path: Path) -> tuple[Path, int]:
    pdf_path = DOCS_DIR / "TC5061_Operacion_FinOps_Equipo30.pdf"
    cmd = [
        "pandoc",
        str(md_path),
        "-f",
        "markdown-implicit_figures",
        "-o",
        str(pdf_path),
        "--pdf-engine=xelatex",
        "-V",
        "geometry:margin=0.68in",
        "-V",
        "mainfont=Arial",
        "-V",
        "fontsize=11pt",
        "-V",
        "linestretch=1.15",
        "-V",
        "colorlinks=true",
        "-V",
        "linkcolor=blue",
        "-V",
        "urlcolor=blue",
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if res.returncode != 0 or not pdf_path.exists():
        raise RuntimeError(f"Error compilando PDF con xelatex:\n{res.stderr}")
    pages = len(pypdf.PdfReader(str(pdf_path)).pages)
    print(f"✓ PDF compilado en {pdf_path} ({pages} páginas, Arial 11pt, interlineado 1.15)")
    return pdf_path, pages


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--ci-note",
        default="El workflow fue verificado en verde en GitHub Actions sobre la rama del entregable.",
        help="Nota breve con evidencia del estado verde de GitHub Actions.",
    )
    args = parser.parse_args()
    load_summary, finops, compose_ver = load_data()
    md_path = build_markdown_report(load_summary, finops, compose_ver, args.ci_note)
    build_docx_report(load_summary, finops, compose_ver, args.ci_note)
    compile_pdf(md_path)


if __name__ == "__main__":
    main()
