"""Script para generar el Reporte Oficial de la Semana 8 en formato DOCX, Markdown y PDF.

Sigue las convenciones y estilo corporativo/académico del Tecnológico de Monterrey
utilizado en las entregas anteriores del Equipo 30.
"""

import os
import subprocess
from pathlib import Path
import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn

DOCS_DIR = Path("docs")
REPORTS_DIR = Path("reports")
FIGURES_DIR = Path("reports/figures")

AZUL_TEC = RGBColor(0, 51, 102)     # #003366
GRIS_TEXTO = RGBColor(51, 65, 85)   # #334155
GRIS_CLARO = "F1F5F9"
AZUL_FONDO = "E0F2FE"


def set_cell_background(cell, fill_hex):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{fill_hex}"/>')
    tcPr.append(shd)


def set_cell_margins(cell, top=100, bottom=100, left=150, right=150):
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = OxmlElement('w:tcMar')
    for m, val in [('top', top), ('bottom', bottom), ('left', left), ('right', right)]:
        node = OxmlElement(f'w:{m}')
        node.set(qn('w:w'), str(val))
        node.set(qn('w:type'), 'dxa')
        tcMar.append(node)
    tcPr.append(tcMar)


def build_docx_report():
    doc = docx.Document()

    # Configuración de márgenes de página (1 pulgada)
    for section in doc.sections:
        section.top_margin = Inches(1.0)
        section.bottom_margin = Inches(1.0)
        section.left_margin = Inches(1.0)
        section.right_margin = Inches(1.0)

    # Estilos por defecto
    normal_style = doc.styles['Normal']
    normal_style.font.name = 'Calibri'
    normal_style.font.size = Pt(11)
    normal_style.font.color.rgb = GRIS_TEXTO

    # 1. ENCABEZADO INSTITUCIONAL
    p_inst = doc.add_paragraph()
    p_inst.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_inst = p_inst.add_run("TECNOLÓGICO DE MONTERREY\nMAESTRÍA EN INTELIGENCIA ARTIFICIAL APLICADA")
    r_inst.font.size = Pt(12)
    r_inst.font.bold = True
    r_inst.font.color.rgb = AZUL_TEC

    p_sub = doc.add_paragraph()
    p_sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_sub = p_sub.add_run("TC5061 — Operaciones de Inteligencia Artificial (MLOps)\nEntrega de Semana 8: Despliegue de Modelos de ML (FastAPI + Contenedores Docker / Podman)")
    r_sub.font.size = Pt(10)
    r_sub.font.color.rgb = RGBColor(100, 116, 139)

    # Línea divisoria
    p_line = doc.add_paragraph()
    p_line.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_line = p_line.add_run("―" * 58)
    r_line.font.color.rgb = RGBColor(203, 213, 225)

    # Título principal del reporte
    p_title = doc.add_paragraph()
    p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_title = p_title.add_run("Reporte Técnico y Ejecutivo: Empaquetado y Despliegue Contenerizado del Microservicio MiBici")
    r_title.font.size = Pt(16)
    r_title.font.bold = True
    r_title.font.color.rgb = AZUL_TEC

    # 2. TABLA DE METADATOS
    table_meta = doc.add_table(rows=4, cols=2)
    table_meta.alignment = WD_TABLE_ALIGNMENT.CENTER
    table_meta.autofit = False

    meta_data = [
        ("Proyecto / Sistema:", "Plataforma de Inteligencia Operativa MiBici (Área Metropolitana de Guadalajara)"),
        ("Repositorio Oficial GitHub:", "https://github.com/Diegob059/TC5061-Proyecto-Equipo30"),
        ("Microservicio Desplegado:", "FastAPI 0.162.0 + Uvicorn 0.54.0 | Modelo: mibici-equipo30-p2-riesgo@champion"),
        ("Fecha de Entrega:", "Noviembre de 2026 — Equipo 30"),
    ]

    for i, (k, v) in enumerate(meta_data):
        row = table_meta.rows[i]
        c0, c1 = row.cells[0], row.cells[1]
        c0.width = Inches(2.2)
        c1.width = Inches(4.3)
        c0.text = k
        c1.text = v
        c0.paragraphs[0].runs[0].font.bold = True
        c0.paragraphs[0].runs[0].font.size = Pt(9.5)
        c1.paragraphs[0].runs[0].font.size = Pt(9.5)
        set_cell_background(c0, GRIS_CLARO)
        set_cell_background(c1, "FFFFFF")
        set_cell_margins(c0, 60, 60, 100, 100)
        set_cell_margins(c1, 60, 60, 100, 100)

    doc.add_paragraph()

    # 3. TABLA DE INTEGRANTES
    p_team_h = doc.add_paragraph()
    r_team_h = p_team_h.add_run("1. Integrantes del Equipo (Equipo 30)")
    r_team_h.font.size = Pt(13)
    r_team_h.font.bold = True
    r_team_h.font.color.rgb = AZUL_TEC

    table_team = doc.add_table(rows=5, cols=3)
    table_team.alignment = WD_TABLE_ALIGNMENT.CENTER

    headers = ["Nombre del Integrante", "Matrícula", "Rol en el Proyecto"]
    for j, h in enumerate(headers):
        cell = table_team.rows[0].cells[j]
        cell.text = h
        cell.paragraphs[0].runs[0].font.bold = True
        cell.paragraphs[0].runs[0].font.size = Pt(9.5)
        cell.paragraphs[0].runs[0].font.color.rgb = RGBColor(255, 255, 255)
        set_cell_background(cell, "003366")
        set_cell_margins(cell, 80, 80, 100, 100)

    team_data = [
        ("Ricardo Bahamón", "A01840023", "MLOps, Pipeline Engineer & Deployment (API, Dockerfile, Makefile, Verificación)"),
        ("Diego Becerril", "A01748115", "Lead Data Scientist & Modeling (Formulación de Target, LightGBM, Pydantic Schema)"),
        ("Gregorio Escobedo Straffon", "A01840612", "Data Engineer & Quality QA (Ingesta Parquet, DeepChecks, Regresión)"),
        ("Freddin Alcántara", "A01797741", "Product & Deployment Lead (Requisitos Operativos CCO, ML Canvas, API Base)"),
    ]

    for i, row_data in enumerate(team_data, start=1):
        row = table_team.rows[i]
        for j, val in enumerate(row_data):
            cell = row.cells[j]
            cell.text = val
            cell.paragraphs[0].runs[0].font.size = Pt(9.5)
            fill = GRIS_CLARO if i % 2 == 1 else "FFFFFF"
            set_cell_background(cell, fill)
            set_cell_margins(cell, 60, 60, 100, 100)

    doc.add_paragraph()

    # 4. RESUMEN EJECUTIVO
    p_sec2 = doc.add_paragraph()
    r_sec2 = p_sec2.add_run("2. Resumen Ejecutivo y Propósito del Microservicio")
    r_sec2.font.size = Pt(13)
    r_sec2.font.bold = True
    r_sec2.font.color.rgb = AZUL_TEC

    p_desc = doc.add_paragraph(
        "En esta actividad integradora, el Equipo 30 da el primer paso hacia la producción industrial del proyecto "
        "MiBici mediante el empaquetado de su modelo de predicción de riesgo operativo (Pregunta 2) como un servicio "
        "REST interactivo, portable y reproducible en cualquier entorno mediante contenedores OCI (Docker y Podman). "
        "El microservicio expone el clasificador entrenado sobre más de 7.89 millones de viajes históricos, permitiendo al "
        "Centro de Control Operativo (CCO) de MiBici anticipar condiciones de desabasto (vaciado) o saturación (llenado) "
        "en las 470 estaciones activas con un horizonte táctico de 2 horas."
    )

    # 5. RECUPERACIÓN DEL MODELO DESDE EL MODEL REGISTRY
    p_sec3 = doc.add_paragraph()
    r_sec3 = p_sec3.add_run("3. Recuperación del Modelo desde el Model Registry (MLflow)")
    r_sec3.font.size = Pt(13)
    r_sec3.font.bold = True
    r_sec3.font.color.rgb = AZUL_TEC

    doc.add_paragraph(
        "La integración del modelo en la API se realizó bajo un patrón desacoplado y gobernado (api/model_loader.py):"
    )
    b1 = doc.add_paragraph(style='List Bullet')
    b1.add_run("Carga por Alias 'champion': ").bold = True
    b1.add_run("Se recupera dinámicamente 'models:/mibici-equipo30-p2-riesgo@champion', resolviendo a la versión "
               "lgbm_profundo (Run ID: 4dcbff8784a348a19f087a0697896be7), seleccionada por su óptimo balance F1 macro "
               "y recall en clases minoritarias.")

    b2 = doc.add_paragraph(style='List Bullet')
    b2.add_run("Configuración desacoplada (MLFLOW_TRACKING_URI): ").bold = True
    b2.add_run("Dentro del contenedor, la ubicación del Model Registry se inyecta mediante la variable de entorno "
               "MLFLOW_TRACKING_URI (apuntando a http://host.containers.internal:5000 en Podman o http://host.docker.internal:5001 "
               "en Docker bajo macOS para evitar colisión con AirPlay). Esta decisión desacopla el ciclo de vida del software "
               "del ciclo de vida del modelo.")

    b3 = doc.add_paragraph(style='List Bullet')
    b3.add_run("Ventajas operativas: ").bold = True
    b3.add_run("La imagen OCI permanece inmutable y ligera (~350 MB). Si se promueve un nuevo modelo campeón en MLflow, "
               "no se requiere reconstruir la imagen ni reiniciar la infraestructura (Rollback y promoción sin downtime).")

    # 6. CONSTRUCCIÓN DE LA API REST CON FASTAPI Y VALIDACIÓN PYDANTIC
    p_sec4 = doc.add_paragraph()
    r_sec4 = p_sec4.add_run("4. Construcción de la API REST con FastAPI y Validación Pydantic v2")
    r_sec4.font.size = Pt(13)
    r_sec4.font.bold = True
    r_sec4.font.color.rgb = AZUL_TEC

    doc.add_paragraph(
        "La API implementada en api/main.py está construida con FastAPI bajo el estándar OpenAPI 3.1 y ASGI Uvicorn:"
    )

    table_endpoints = doc.add_table(rows=6, cols=3)
    table_endpoints.alignment = WD_TABLE_ALIGNMENT.CENTER
    ep_headers = ["Método", "Endpoint", "Propósito y Funcionalidad"]
    for j, h in enumerate(ep_headers):
        cell = table_endpoints.rows[0].cells[j]
        cell.text = h
        cell.paragraphs[0].runs[0].font.bold = True
        cell.paragraphs[0].runs[0].font.size = Pt(9.5)
        cell.paragraphs[0].runs[0].font.color.rgb = RGBColor(255, 255, 255)
        set_cell_background(cell, "003366")
        set_cell_margins(cell, 80, 80, 100, 100)

    ep_data = [
        ("GET", "/", "Comprobación básica de disponibilidad y nombre del modelo registrado."),
        ("GET", "/health", "Health check operativo para sondas de orquestadores y balanceadores (HTTP 200)."),
        ("GET", "/model-info", "Metadatos detallados de linaje, alias, horizonte temporal (2h) y tracking URI."),
        ("POST", "/predict", "Inferencia de clasificación de riesgo en tiempo real (0: Normal, 1: Desabasto, 2: Saturación)."),
        ("GET", "/docs", "Documentación interactiva Swagger UI con ejemplos reales de Guadalajara."),
    ]
    for i, row_data in enumerate(ep_data, start=1):
        row = table_endpoints.rows[i]
        for j, val in enumerate(row_data):
            cell = row.cells[j]
            cell.text = val
            cell.paragraphs[0].runs[0].font.size = Pt(9.5)
            fill = GRIS_CLARO if i % 2 == 1 else "FFFFFF"
            set_cell_background(cell, fill)
            set_cell_margins(cell, 60, 60, 100, 100)

    doc.add_paragraph()

    doc.add_paragraph(
        "Validación robusta con Pydantic v2 (PredictionInput):"
    )
    b_val1 = doc.add_paragraph(style='List Bullet')
    b_val1.add_run("Restricciones físicas: ").bold = True
    b_val1.add_run("capacity > 0 (anclajes físicos), latitud [-90, 90], longitud [-180, 180], flujos históricos >= 0, "
                   "senos y cosenos cíclicos [-1, 1], y allow_inf_nan=False.")

    b_val2 = doc.add_paragraph(style='List Bullet')
    b_val2.add_run("Protección contra inyección (extra='forbid'): ").bold = True
    b_val2.add_run("Cualquier carga útil que contenga campos ajenos a las 17 variables predictoras del modelo es rechazada "
                   "automáticamente con código HTTP 422 Unprocessable Entity.")

    b_val3 = doc.add_paragraph(style='List Bullet')
    b_val3.add_run("Resolución de Incompatibilidad de Esquema MLflow (Bugfix Crítico): ").bold = True
    b_val3.add_run("Se implementó una conversión explícita de tipos antes de llamar a model.predict(X): capacity se castea a int32 "
                   "y las características continuas a float32, resolviendo la incompatibilidad estricta de schema que provocaba "
                   "errores HTTP 500 al recibir float64.")

    # 7. CONTENERIZACIÓN OCI CON DOCKER / PODMAN
    p_sec5 = doc.add_paragraph()
    r_sec5 = p_sec5.add_run("5. Contenerización OCI con Docker y Podman (Dockerfile / Containerfile)")
    r_sec5.font.size = Pt(13)
    r_sec5.font.bold = True
    r_sec5.font.color.rgb = AZUL_TEC

    doc.add_paragraph(
        "Se implementaron Dockerfile y Containerfile sincronizados bajo el estándar Open Container Initiative (OCI):"
    )
    b_cont1 = doc.add_paragraph(style='List Bullet')
    b_cont1.add_run("Imagen Base: ").bold = True
    b_cont1.add_run("python:3.12-slim, minimizando vulnerabilidades y reduciendo el tamaño a ~350 MB.")

    b_cont2 = doc.add_paragraph(style='List Bullet')
    b_cont2.add_run("Soporte OpenMP para LightGBM: ").bold = True
    b_cont2.add_run("Instalación de libgomp1 mediante apt-get, requisito nativo indispensable para ejecutar el runtime de LightGBM en Linux.")

    b_cont3 = doc.add_paragraph(style='List Bullet')
    b_cont3.add_run("Aislamiento de Dependencias: ").bold = True
    b_cont3.add_run("requirements-api.txt incluye únicamente las 10 dependencias de inferencia (FastAPI, Uvicorn, Pydantic, MLflow, LightGBM, scikit-learn, pandas, numpy, pyasn1 y python-dotenv).")

    b_cont4 = doc.add_paragraph(style='List Bullet')
    b_cont4.add_run("HEALTHCHECK Integrado: ").bold = True
    b_cont4.add_run("Sondeo automático cada 30 segundos sobre http://localhost:8000/health para autoreparación en orquestadores.")

    b_cont5 = doc.add_paragraph(style='List Bullet')
    b_cont5.add_run("Automatización en Makefile: ").bold = True
    b_cont5.add_run("Comandos 'make build_container', 'make run_container', 'make test_api_live' y 'make stop_container' con detección automática del motor disponible (docker o podman).")

    # 8. VERIFICACIÓN Y EVIDENCIAS
    p_sec6 = doc.add_paragraph()
    r_sec6 = p_sec6.add_run("6. Resultados de Verificación, Pruebas Unitarias y Evidencia")
    r_sec6.font.size = Pt(13)
    r_sec6.font.bold = True
    r_sec6.font.color.rgb = AZUL_TEC

    doc.add_paragraph(
        "El microservicio fue sometido a validación rigurosa mediante dos mecanismos complementarios:"
    )
    b_t1 = doc.add_paragraph(style='List Bullet')
    b_t1.add_run("Suite de Pruebas Unitarias (pytest): ").bold = True
    b_t1.add_run("62 pruebas pasando al 100% en 13.04 segundos, incluyendo las 8 pruebas de validación de endpoints y esquema de tests/test_api.py.")

    b_t2 = doc.add_paragraph(style='List Bullet')
    b_t2.add_run("Sondeo Automatizado en Vivo (scripts/verify_container_api.py): ").bold = True
    b_t2.add_run("6 comprobaciones automáticas contra el servicio activo (reports/container_verification.json). La latencia media de inferencia fue de 5.02 ms.")

    # Imagen de evidencia
    img_path = FIGURES_DIR / "semana8_api_container_evidence.png"
    if img_path.exists():
        p_img = doc.add_paragraph()
        p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
        doc.add_picture(str(img_path), width=Inches(6.2))
        p_cap = doc.add_paragraph()
        p_cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r_cap = p_cap.add_run("Figura 1: Evidencia de verificación del contenedor OCI y respuesta en vivo de la API REST.")
        r_cap.font.size = Pt(9)
        r_cap.font.italic = True

    # 9. JUSTIFICACIÓN TEÓRICA Y ESTRATÉGICA DE DESPLIEGUE
    p_sec7 = doc.add_paragraph()
    r_sec7 = p_sec7.add_run("7. Justificación Teórica y Estratégica del Despliegue")
    r_sec7.font.size = Pt(13)
    r_sec7.font.bold = True
    r_sec7.font.color.rgb = AZUL_TEC

    doc.add_paragraph(
        "Con base en la literatura fundamental de MLOps (Chip Huyen, 2022, Cap. 7; Treveil et al., 2020, Cap. 6), se "
        "justifican las siguientes decisiones de diseño arquitectónico:"
    )

    b_j1 = doc.add_paragraph(style='List Bullet')
    b_j1.add_run("Inferencia en Tiempo Real (Online) para la Pregunta 2: ").bold = True
    b_j1.add_run("La movilidad de bicicletas compartidas en Guadalajara sufre fluctuaciones estocásticas imprevistas (lluvia, eventos masivos, cierres viales). "
               "Los despachadores del CCO necesitan evaluar el riesgo inminente de una estación bajo demanda para desviar camiones de rebalanceo en caliente. "
               "La API REST proporciona respuestas sub-segundo (< 10 ms) directamente integrables con tableros operativos.")

    b_j2 = doc.add_paragraph(style='List Bullet')
    b_j2.add_run("Arquitectura Híbrida (Complementariedad con Batch): ").bold = True
    b_j2.add_run("Mientras que la Pregunta 2 opera en tiempo real, las Preguntas 1 (cálculo de inventario inicial de bicicletas) y 3 (segmentación de estaciones) "
               "se ejecutan como trabajos por lotes (Batch) programados a las 04:00 AM. Este enfoque híbrido evita sobrecostos de infraestructura en la nube "
               "y asigna el patrón óptimo a cada necesidad de negocio.")

    # 10. TRABAJO COLABORATIVO EN GIT
    p_sec8 = doc.add_paragraph()
    r_sec8 = p_sec8.add_run("8. Trabajo Colaborativo en Git y Gestión de Pull Requests")
    r_sec8.font.size = Pt(13)
    r_sec8.font.bold = True
    r_sec8.font.color.rgb = AZUL_TEC

    doc.add_paragraph(
        "Siguiendo la política de GitHub Flow y Conventional Commits del equipo, la entrega se organizó en ramas temáticas "
        "revisadas y fusionadas mediante Pull Requests formales en el repositorio oficial:"
    )

    prs = [
        ("PR #34", "fix(api): robustecer validación de esquema MLflow y enriquecer endpoints de salud y metadatos", "Ricardo Bahamón"),
        ("PR #35", "feat(container): estandarizar Dockerfile OCI y automatizar ciclo de vida en Makefile", "Ricardo Bahamón"),
        ("PR #36", "docs(readme): guía de despliegue contenerizado y justificación de inferencia en tiempo real", "Ricardo Bahamón"),
        ("PR #37", "test(container): añadir verificación automatizada y evidencia de ejecución de la API", "Ricardo Bahamón"),
        ("PR #38", "fix(api): incluir python-dotenv en dependencias del contenedor y blindar importación", "Ricardo Bahamón"),
    ]

    for pr_id, pr_desc, author in prs:
        p_pr = doc.add_paragraph(style='List Bullet')
        p_pr.add_run(f"{pr_id}: ").bold = True
        p_pr.add_run(f"{pr_desc} (Autor: {author}).")

    # 11. CONCLUSIONES
    p_sec9 = doc.add_paragraph()
    r_sec9 = p_sec9.add_run("9. Conclusiones y Próximos Pasos")
    r_sec9.font.size = Pt(13)
    r_sec9.font.bold = True
    r_sec9.font.color.rgb = AZUL_TEC

    doc.add_paragraph(
        "La Semana 8 concluye con la exitosa transformación del modelo de machine learning en un servicio consumible, "
        "empaquetado en un contenedor estándar OCI que garantiza reproducibilidad entre entornos de desarrollo y producción. "
        "Esta base técnica permite al equipo abordar en la siguiente etapa la orquestación distribuida de microservicios, el "
        "monitoreo continuo de deriva en producción (Drift Monitoring) y los pipelines de CI/CD automatizados."
    )

    docx_path = DOCS_DIR / "TC5061_Reporte_Despliegue_Contenedores_Equipo30.docx"
    doc.save(str(docx_path))
    print(f"✓ Documento Word guardado exitosamente en: {docx_path}")
    return docx_path


def build_markdown_report():
    md_content = r"""# TECNOLÓGICO DE MONTERREY
## Maestría en Inteligencia Artificial Aplicada
### TC5061 — Operaciones de Inteligencia Artificial (MLOps)
**Entrega de Semana 8: Despliegue de Modelos de ML (FastAPI + Contenedores Docker / Podman)**

---

# Reporte Técnico y Ejecutivo: Empaquetado y Despliegue Contenerizado del Microservicio MiBici

## Metadatos del Proyecto

| Campo | Valor |
| :--- | :--- |
| **Proyecto / Sistema:** | Plataforma de Inteligencia Operativa MiBici (Área Metropolitana de Guadalajara) |
| **Repositorio Oficial GitHub:** | [https://github.com/Diegob059/TC5061-Proyecto-Equipo30](https://github.com/Diegob059/TC5061-Proyecto-Equipo30) |
| **Microservicio Desplegado:** | FastAPI 0.162.0 + Uvicorn 0.54.0 \| Modelo: `mibici-equipo30-p2-riesgo@champion` |
| **Fecha de Entrega:** | Noviembre de 2026 — Equipo 30 |

## 1. Integrantes del Equipo (Equipo 30)

| Nombre del Integrante | Matrícula | Rol en el Proyecto |
| :--- | :--- | :--- |
| **Ricardo Bahamón** | A01840023 | MLOps, Pipeline Engineer & Deployment (API, Dockerfile, Makefile, Verificación) |
| **Diego Becerril** | A01748115 | Lead Data Scientist & Modeling (Formulación de Target, LightGBM, Pydantic Schema) |
| **Gregorio Escobedo Straffon** | A01840612 | Data Engineer & Quality QA (Ingesta Parquet, DeepChecks, Regresión) |
| **Freddin Alcántara** | A01797741 | Product & Deployment Lead (Requisitos Operativos CCO, ML Canvas, API Base) |

---

## 2. Resumen Ejecutivo y Propósito del Microservicio

En esta actividad integradora, el Equipo 30 da el primer paso hacia la producción industrial del proyecto MiBici mediante el empaquetado de su modelo de predicción de riesgo operativo (**Pregunta 2**) como un servicio REST interactivo, portable y reproducible en cualquier entorno mediante contenedores OCI (Docker y Podman).

El microservicio expone el clasificador entrenado sobre más de **7.89 millones de viajes históricos**, permitiendo al Centro de Control Operativo (CCO) de MiBici anticipar condiciones de **desabasto** (vaciado) o **saturación** (llenado) en las 470 estaciones activas con un horizonte táctico de **2 horas**.

---

## 3. Recuperación del Modelo desde el Model Registry (MLflow)

La integración del modelo en la API se realizó bajo un patrón desacoplado y gobernado (`api/model_loader.py`):

* **Carga por Alias `@champion`:** Se recupera dinámicamente `models:/mibici-equipo30-p2-riesgo@champion`, resolviendo a la versión `lgbm_profundo` (Run ID: `4dcbff8784a348a19f087a0697896be7`), seleccionada por su óptimo balance F1 macro y recall en clases minoritarias.
* **Configuración desacoplada (`MLFLOW_TRACKING_URI`):** Dentro del contenedor, la ubicación del Model Registry se inyecta mediante la variable de entorno `MLFLOW_TRACKING_URI` (apuntando a `http://host.containers.internal:5000` en Podman o `http://host.docker.internal:5001` en Docker bajo macOS para evitar colisión con AirPlay).
* **Ventajas operativas:** La imagen OCI permanece inmutable y ligera (~350 MB). Si se promueve un nuevo modelo campeón en MLflow, no se requiere reconstruir la imagen ni reiniciar la infraestructura (Rollback y promoción sin downtime).

---

## 4. Construcción de la API REST con FastAPI y Validación Pydantic v2

La API implementada en `api/main.py` está construida con FastAPI bajo el estándar OpenAPI 3.1 y servidor ASGI Uvicorn:

### Endpoints Disponibles

| Método | Endpoint | Propósito y Funcionalidad |
| :--- | :--- | :--- |
| `GET` | `/` | Comprobación básica de disponibilidad y nombre del modelo registrado. |
| `GET` | `/health` | Health check operativo para orquestadores y balanceadores (HTTP 200). |
| `GET` | `/model-info` | Metadatos detallados de linaje, alias, horizonte temporal (2h) y tracking URI. |
| `POST` | `/predict` | Inferencia de clasificación de riesgo en tiempo real (0: Normal, 1: Desabasto, 2: Saturación). |
| `GET` | `/docs` | Documentación interactiva Swagger UI con ejemplos reales de Guadalajara. |

### Validación Robusta con Pydantic v2 (`PredictionInput`)

* **Restricciones físicas:** `capacity > 0` (anclajes físicos), latitud `[-90, 90]`, longitud `[-180, 180]`, flujos históricos `>= 0`, senos y cosenos cíclicos `[-1, 1]`, y `allow_inf_nan=False`.
* **Protección contra inyección (`extra="forbid"`):** Cualquier carga útil que contenga campos ajenos a las 17 variables predictoras del modelo es rechazada automáticamente con código **HTTP 422 Unprocessable Entity**.
* **Resolución de Incompatibilidad de Esquema MLflow (Bugfix Crítico):** Se implementó una conversión explícita de tipos antes de llamar a `model.predict(X)`: `capacity` se castea a `int32` y las características continuas a `float32`, resolviendo la incompatibilidad estricta de schema que provocaba errores HTTP 500 al recibir `float64`.

---

## 5. Contenerización OCI con Docker y Podman (Dockerfile / Containerfile)

Se implementaron `Dockerfile` y `Containerfile` sincronizados bajo el estándar Open Container Initiative (OCI):

* **Imagen Base:** `python:3.12-slim`, minimizando vulnerabilidades y reduciendo el tamaño a ~350 MB.
* **Soporte OpenMP para LightGBM:** Instalación de `libgomp1` mediante `apt-get`, requisito nativo indispensable para ejecutar el runtime de LightGBM en Linux.
* **Aislamiento de Dependencias:** `requirements-api.txt` incluye únicamente las 10 dependencias de inferencia (`fastapi`, `uvicorn`, `pydantic`, `mlflow`, `lightgbm`, `scikit-learn`, `pandas`, `numpy`, `pyasn1` y `python-dotenv`).
* **HEALTHCHECK Integrado:** Sondeo automático cada 30 segundos sobre `http://localhost:8000/health` para autoreparación en orquestadores.
* **Automatización en Makefile:** Comandos `make build_container`, `make run_container`, `make test_api_live` y `make stop_container` con detección automática del motor disponible (`docker` o `podman`).

---

## 6. Resultados de Verificación, Pruebas Unitarias y Evidencia

El microservicio fue sometido a validación rigurosa mediante dos mecanismos complementarios:

1. **Suite de Pruebas Unitarias (`pytest`):** **62 pruebas pasando al 100% en 13.04 segundos**, incluyendo las 8 pruebas de validación de endpoints y esquema de `tests/test_api.py`.
2. **Sondeo Automatizado en Vivo (`scripts/verify_container_api.py`):** 6 comprobaciones automáticas contra el servicio activo (`reports/container_verification.json`). La latencia media de inferencia fue de **5.02 ms** (muy por debajo del umbral operacional de 50 ms).

### Evidencia Visual del Contenedor Activo

![Evidencia de verificación del contenedor OCI y respuesta en vivo de la API REST](../reports/figures/semana8_api_container_evidence.png)

---

## 7. Justificación Teórica y Estratégica del Despliegue

Con base en la literatura fundamental de MLOps (*Chip Huyen, 2022, Cap. 7; Treveil et al., 2020, Cap. 6*), se justifican las siguientes decisiones de diseño arquitectónico:

* **Inferencia en Tiempo Real (Online) para la Pregunta 2:** La movilidad de bicicletas compartidas en Guadalajara sufre fluctuaciones estocásticas imprevistas (lluvia, eventos masivos, cierres viales). Los despachadores del CCO necesitan evaluar el riesgo inminente de una estación bajo demanda para desviar camiones de rebalanceo en caliente. La API REST proporciona respuestas sub-segundo (< 10 ms) directamente integrables con tableros operativos.
* **Arquitectura Híbrida (Complementariedad con Batch):** Mientras que la Pregunta 2 opera en tiempo real, las Preguntas 1 (cálculo de inventario inicial de bicicletas) y 3 (segmentación de estaciones) se ejecutan como trabajos por lotes (Batch) programados a las 04:00 AM. Este enfoque híbrido evita sobrecostos de infraestructura en la nube y asigna el patrón óptimo a cada necesidad de negocio.

---

## 8. Trabajo Colaborativo en Git y Gestión de Pull Requests

Siguiendo la política de GitHub Flow y Conventional Commits del equipo, la entrega se organizó en ramas temáticas revisadas y fusionadas mediante Pull Requests formales en el repositorio oficial:

* **PR #34:** `fix(api): robustecer validación de esquema MLflow y enriquecer endpoints de salud y metadatos` (Autor: Ricardo Bahamón).
* **PR #35:** `feat(container): estandarizar Dockerfile OCI y automatizar ciclo de vida en Makefile` (Autor: Ricardo Bahamón).
* **PR #36:** `docs(readme): guía de despliegue contenerizado y justificación de inferencia en tiempo real` (Autor: Ricardo Bahamón).
* **PR #37:** `test(container): añadir verificación automatizada y evidencia de ejecución de la API` (Autor: Ricardo Bahamón).
* **PR #38:** `fix(api): incluir python-dotenv en dependencias del contenedor y blindar importación` (Autor: Ricardo Bahamón).

---

## 9. Conclusiones y Próximos Pasos

La Semana 8 concluye con la exitosa transformación del modelo de machine learning en un servicio consumible, empaquetado en un contenedor estándar OCI que garantiza reproducibilidad entre entornos de desarrollo y producción. Esta base técnica permite al equipo abordar en la siguiente etapa la orquestación distribuida de microservicios, el monitoreo continuo de deriva en producción (Drift Monitoring) y los pipelines de CI/CD automatizados.
"""
    md_path = DOCS_DIR / "TC5061_Reporte_Despliegue_Contenedores_Equipo30.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_content)
    print(f"✓ Documento Markdown guardado exitosamente en: {md_path}")
    return md_path


def compile_pdf_report(md_path):
    pdf_path = DOCS_DIR / "TC5061_Reporte_Despliegue_Contenedores_Equipo30.pdf"
    cmd = [
        "pandoc",
        str(md_path),
        "-o",
        str(pdf_path),
        "--pdf-engine=xelatex",
        "-V", "geometry:margin=1in",
        "-V", "mainfont=Helvetica",
        "-V", "fontsize=11pt",
        "-V", "colorlinks=true",
        "-V", "linkcolor=blue",
        "-V", "urlcolor=blue",
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode == 0 and pdf_path.exists():
        print(f"✓ Documento PDF compilado exitosamente en: {pdf_path}")
    else:
        print(f"Aviso al compilar PDF con xelatex: {res.stderr}")
        # Fallback a pdflatex si xelatex requiere alguna fuente específica
        cmd_fallback = [
            "pandoc",
            str(md_path),
            "-o",
            str(pdf_path),
            "--pdf-engine=pdflatex",
            "-V", "geometry:margin=1in",
            "-V", "fontsize=11pt",
        ]
        res_fb = subprocess.run(cmd_fallback, capture_output=True, text=True)
        if res_fb.returncode == 0:
            print(f"✓ Documento PDF compilado con pdflatex en: {pdf_path}")
        else:
            print(f"Error en fallback: {res_fb.stderr}")


if __name__ == "__main__":
    docx_file = build_docx_report()
    md_file = build_markdown_report()
    compile_pdf_report(md_file)
