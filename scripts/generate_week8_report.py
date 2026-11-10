"""Genera el reporte de Semana 8 en Word y Markdown desde evidencia verificada.

El PDF se exporta desde el documento Word. Requiere python-docx y Pillow.
"""

import hashlib
import json
import re
from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
NAME = "TC5061_Reporte_Despliegue_Contenedores_Equipo30"
REPO_URL = "https://github.com/Diegob059/TC5061-Proyecto-Equipo30"
MEMBERS = [
    ("Ricardo Bahamón", "A01840023"),
    ("Diego Becerril", "A01748115"),
    ("Gregorio Escobedo Straffon", "A01840612"),
    ("Freddin Alcántara", "A01797741"),
]


def load_evidence():
    data = json.loads((ROOT / "reports/container_verification.json").read_text())
    registry = json.loads(
        (ROOT / "reports/semana8/registry_validation.json").read_text()
    )
    capture = json.loads((ROOT / "reports/semana8/capture_provenance.json").read_text())
    image = ROOT / "reports/figures/semana8_api_container_evidence.png"
    if data.get("evidence_scope") != "container_and_http" or not data.get(
        "container", {}
    ).get("passed"):
        raise ValueError(
            "Se requiere verificación real del contenedor antes de generar este reporte"
        )
    if data["overall_status"] != "PASS":
        raise ValueError("La verificación del servicio no aprobó")
    if hashlib.sha256(image.read_bytes()).hexdigest() != capture["sha256"]:
        raise ValueError("La captura no coincide con su registro de procedencia")
    return data, registry


def content(data, registry):
    prediction = next(
        t
        for t in data["tests"]
        if t["endpoint"] == "/predict" and t["expected_code"] == 200
    )
    container = data["container"]
    unit = json.loads((ROOT / "reports/semana8/execution.json").read_text())
    sample = prediction["request_payload"]
    runtime = json.loads((ROOT / "reports/semana8/container-image.json").read_text())
    return f"""## 1 API y modelo registrado

El proyecto MiBici expone el clasificador de riesgo de P2 mediante FastAPI. El endpoint recibe las 17 variables predictoras de una estación y devuelve una clase en JSON. La ejecución documentada verificó el servicio dentro de Podman y la recuperación del modelo desde MLflow Model Registry.

Para esta verificación se reconstruyó localmente LightGBM con la configuración lgbm_profundo y {registry["training_rows"]:,} filas reales de Train, anteriores al corte {registry["training_cutoff"]}. La versión {registry["version"]} se registró como mibici-equipo30-p2-riesgo con alias champion. Esta reconstrucción tiene su propio run; las métricas y artefactos históricos del equipo se conservan por separado.

| Identificador | Valor verificado |
|---|---|
| Model URI | {registry["model_uri"]} |
| Run de validación | {registry["source_run_id"]} |
| Datos procesados SHA256 | {registry["data_sha256"]} |

| Método | Endpoint | Función |
|---|---|---|
| GET | / | Estado básico y nombre del modelo |
| GET | /health | Disponibilidad del servicio |
| GET | /model-info | Configuración de carga del modelo |
| POST | /predict | Clasificación de riesgo en JSON |
| GET | /docs | Contrato OpenAPI y pruebas desde Swagger |

capacity debe representar un entero positivo compatible con int32. Las demás variables se validan como valores finitos compatibles con float32, con límites para coordenadas, lags y codificaciones cíclicas. Se rechazan campos extra, faltantes y valores que perderían validez al convertir sus tipos. Las entradas inválidas devuelven HTTP 422 antes de invocar el modelo.

## 2 Contenerización y estrategia de despliegue

Containerfile y Dockerfile utilizan Python 3.12 slim, libgomp1 y las versiones de requirements-api.txt. SQLAlchemy se fija a 2.0.44, compatible con MLflow 3.5.0 y con el entorno principal del proyecto. La construcción con Podman utiliza --format=docker para conservar HEALTHCHECK, que consulta /health cada 30 segundos.

Los siguientes comandos construyen y ejecutan el servicio con Podman. MLflow debe tener disponible el modelo registrado y servir sus artefactos por HTTP.

```bash
make mlflow MLFLOW_PORT=5001
# En otra terminal con el entorno del proyecto activo
make build_container CONTAINER_ENGINE=podman
make run_container CONTAINER_ENGINE=podman MLFLOW_PORT=5001
make test_api_live CONTAINER_ENGINE=podman
```

MLFLOW_PORT configura tanto el servidor como la dirección usada por el contenedor. Podman utiliza host.containers.internal; Docker utiliza host.docker.internal y el mapeo host-gateway en Linux. MODEL_URI permite elegir un alias o una versión.

| Medida | Evidencia de la ejecución |
|---|---|
| Motor | {runtime["engine_version"]} |
| Imagen | {container["image_name"]} |
| Tamaño local de la imagen | {runtime["size_bytes"] / 1024**2:.1f} MiB |
| Contenedor | {container["id"][:16]} |
| Estado observado | {container["status"]} con puerto 8000 publicado |

P2 usa inferencia bajo demanda por HTTP porque el cliente puede solicitar una evaluación de riesgo por estación. P1 y P3 conservan sus comandos por lotes. El repositorio no configura una ejecución automática a una hora fija.

El modelo se carga una sola vez al iniciar la API. Si cambia el alias champion, se reinicia el contenedor para cargar la nueva versión. No hace falta reconstruir la imagen mientras el contrato y las dependencias sigan siendo compatibles. Esta implementación no incluye recarga automática del modelo.

## 3 Petición y verificación del servicio

La petición de prueba se envió a POST /predict con los siguientes datos:

```json
{json.dumps(sample, ensure_ascii=False, indent=2)}
```

Respuesta observada con el modelo registrado:

```json
{json.dumps(prediction["response"])}
```

La latencia de esa petición fue {prediction["latency_ms"]} ms. Es una observación local de una petición, no un promedio de carga ni una garantía de latencia en producción. Las clases son 0 normal, 1 riesgo de desabasto y 2 riesgo de saturación, conforme al target de P2.

| Verificación | Resultado observado |
|---|---|
| PyTest del proyecto | {unit["pytest"]["passed"]} aprobadas y {unit["pytest"]["skipped"]} omitidas |
| HTTP del servicio en contenedor | {data["summary"]["passed"]} de {data["summary"]["total"]} comprobaciones aprobadas |
| Auditor contra simulación válida | PASS 10 de 10 y código de salida 0 |
| Auditor contra respuestas 503 | FAIL 0 de 10 y código de salida 1 esperado |

El auditor valida códigos HTTP y contenido JSON. También exige un contenedor activo cuyo puerto publicado coincida con el servicio comprobado. Conserva errores de conexión y validación en JSON y devuelve un código distinto de cero ante fallos. Las simulaciones prueban el comportamiento del auditor y se distinguen de la ejecución con MLflow y el modelo reales.

## 4 Evidencia y contribuciones del equipo

La siguiente captura muestra la API respondiendo desde el servicio contenerizado. Su procedencia y hash se conservan en reports/semana8/capture_provenance.json. El contenedor y su puerto se verificaron mediante la inspección del motor registrada en reports/container_verification.json.

![Respuesta de la API ejecutada en Podman](../reports/figures/semana8_api_container_evidence.png)

| Integrante | Contribución identificable en Git |
|---|---|
| Freddin Alcántara | PR 32 con la API base y carga desde MLflow |
| Diego Becerril | PR 33 con validación de entradas y definición de contenedor |
| Ricardo Bahamón | PR 34 a 40 con integración, contenedores, pruebas y documentación |
| Gregorio Escobedo Straffon | Commit b5b9119 con validación de tipos, puertos, auditor y regresiones; evidencia de ejecución y actualización de este reporte |

El servicio respondió a la petición válida y rechazó las entradas inválidas del conjunto de verificación. Los registros conservan los resultados, la procedencia del modelo y los hashes del código probado. Esta evidencia respalda la ejecución local documentada con el modelo y la imagen identificados.

Fuentes de evidencia: reports/semana8/pytest.xml, pytest.log, registry_validation.json, container-build.log y execution.json; reports/container_verification.json.

Referencias técnicas: FastAPI, FastAPI in Containers, https://fastapi.tiangolo.com/deployment/docker/ ; MLflow, Deploy MLflow Model as a Local Inference Server, https://mlflow.org/docs/latest/ml/deployment/deploy-model-locally/ ; Podman, Installation, https://podman.io/docs/installation .
"""


def plain(text):
    return text.replace("**", "").replace("`", "")


def build_docx(body):
    doc = Document()
    doc.core_properties.author = "Equipo 30"
    doc.core_properties.title = "API REST y contenedores para MiBici"
    section = doc.sections[0]
    section.page_width = Inches(8.5)
    section.page_height = Inches(11)
    section.top_margin = Inches(0.7)
    section.bottom_margin = Inches(0.65)
    section.left_margin = section.right_margin = Inches(0.75)
    section.different_first_page_header_footer = True
    normal = doc.styles["Normal"]
    normal.font.name = "Calibri"
    normal.font.size = Pt(11)
    normal.font.color.rgb = RGBColor(0, 0, 0)
    normal.paragraph_format.space_after = Pt(7)
    normal.paragraph_format.line_spacing = 1.08
    normal.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    for name, size in [("Title", 24), ("Heading 1", 17)]:
        st = doc.styles[name]
        st.font.name = "Calibri"
        st.font.size = Pt(size)
        st.font.bold = True
        st.font.color.rgb = RGBColor(0, 0, 0)
        st.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.LEFT
        st.paragraph_format.space_after = Pt(10)
    header = section.header.paragraphs[0]
    header.text = "TC5061   |   MiBici Guadalajara   |   Equipo 30"
    header.runs[0].font.size = Pt(9)
    footer = section.footer.paragraphs[0]
    footer.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    footer.add_run("Equipo 30  ·  ").font.size = Pt(9)
    field = OxmlElement("w:fldSimple")
    field.set(qn("w:instr"), "PAGE")
    footer._p.append(field)

    def cover(text, size, bold=False, before=0, after=8, style=None):
        p = doc.add_paragraph(text, style)
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_before = Pt(before)
        p.paragraph_format.space_after = Pt(after)
        for r in p.runs:
            r.font.size = Pt(size)
            r.font.bold = bold

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.add_run().add_picture(
        str(ROOT / "docs/assets/logo_tecnologico.png"), width=Inches(1.1)
    )
    cover("TECNOLÓGICO DE MONTERREY", 16, True, after=10)
    cover("Maestría en Inteligencia Artificial Aplicada", 12, after=5)
    cover("TC5061 Operaciones de Inteligencia Artificial", 11, after=0)
    cover(
        "API REST y contenedores\npara MiBici",
        24,
        True,
        before=26,
        after=12,
        style="Title",
    )
    cover(
        "Optimización operativa de la red MiBici Guadalajara\n2025 y 2026", 12, after=18
    )
    cover("Proyecto integrador\nActividad de la semana 8", 13, after=10)
    cover("Equipo 30", 13, True, after=16)
    for name, student in MEMBERS:
        cover(name, 11.5, True, after=2)
        cover(student, 10.5, after=9)
    cover("Verificación del 9 de noviembre de 2026", 11, before=12, after=12)
    cover("Repositorio del proyecto", 10.5, True, after=5)
    cover(REPO_URL, 9.5, after=0)
    lines = body.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
            continue
        if line.startswith("## "):
            p = doc.add_heading(line[3:], 1)
            p.paragraph_format.page_break_before = True
            i += 1
            continue
        if line.startswith("```"):
            code = []
            i += 1
            while i < len(lines) and not lines[i].startswith("```"):
                code.append(lines[i])
                i += 1
            p = doc.add_paragraph("\n".join(code))
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT
            p.paragraph_format.line_spacing = 1
            p.paragraph_format.keep_together = True
            for r in p.runs:
                r.font.name = "Courier New"
                r.font.size = Pt(8.5)
            i += 1
            continue
        if line.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                row = [plain(x.strip()) for x in lines[i].strip("|").split("|")]
                if not all(re.fullmatch("[: -]+", cell) for cell in row):
                    rows.append(row)
                i += 1
            table = doc.add_table(rows=0, cols=len(rows[0]))
            table.alignment = WD_TABLE_ALIGNMENT.CENTER
            for ri, row in enumerate(rows):
                cells = table.add_row().cells
                props = table.rows[-1]._tr.get_or_add_trPr()
                props.append(OxmlElement("w:cantSplit"))
                if ri == 0:
                    props.append(OxmlElement("w:tblHeader"))
                for cell, text in zip(cells, row):
                    cell.text = text
                    sh = OxmlElement("w:shd")
                    sh.set(
                        qn("w:fill"),
                        "203F58"
                        if ri == 0
                        else ("F1F5F8" if ri % 2 == 0 else "FFFFFF"),
                    )
                    cell._tc.get_or_add_tcPr().append(sh)
                    for p in cell.paragraphs:
                        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
                        p.paragraph_format.space_after = Pt(4)
                        for r in p.runs:
                            r.font.size = Pt(9)
                            r.font.bold = ri == 0
                            r.font.color.rgb = RGBColor.from_string(
                                "FFFFFF" if ri == 0 else "000000"
                            )
            doc.add_paragraph().paragraph_format.space_after = Pt(0)
            continue
        if line.startswith("!["):
            match = re.match(r"!\[(.*?)\]\((.*?)\)", line)
            image = (ROOT / "docs" / match[2]).resolve()
            w, h = Image.open(image).size
            width = min(6.8, 3.7 * w / h)
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.keep_with_next = True
            p.add_run().add_picture(str(image), width=Inches(width))
            p = doc.add_paragraph("Figura 1. " + match[1])
            p.runs[0].font.size = Pt(9)
            i += 1
            continue
        p = doc.add_paragraph(plain(line))
        if line.startswith(("Referencias técnicas:", "Fuentes de evidencia:")):
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT
            for r in p.runs:
                r.font.size = Pt(9)
        i += 1
    path = ROOT / "docs" / f"{NAME}.docx"
    for style in doc.styles:
        for border in list(style.element.iter(qn("w:pBdr"))):
            border.getparent().remove(border)
    for border in list(doc.element.iter(qn("w:pBdr"))):
        border.getparent().remove(border)
    doc.save(path)
    return path


def main():
    data, registry = load_evidence()
    body = content(data, registry)
    title = "# API REST y contenedores para MiBici\n\nTecnológico de Monterrey. TC5061. Equipo 30. Verificación del 9 de noviembre de 2026.\n\n"
    (ROOT / "docs" / f"{NAME}.md").write_text(title + body, encoding="utf-8")
    print(build_docx(body))


if __name__ == "__main__":
    main()
