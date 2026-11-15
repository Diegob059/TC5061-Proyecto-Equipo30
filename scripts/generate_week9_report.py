"""Script para generar el Reporte Oficial del Entregable 8 (Drift y A/B Testing) en DOCX, MD y PDF.

Sigue las convenciones y estilo institucional del Tecnológico de Monterrey
utilizado en las entregas del Equipo 30 para la materia TC5061 (MLOps).
Genera:
- `docs/TC5061_Drift_ABTest_Equipo30.docx`
- `docs/TC5061_Drift_ABTest_Equipo30.md`
- `docs/TC5061_Drift_ABTest_Equipo30.pdf` (exactamente entre 3 y 5 cuartillas conforme a rúbrica)
"""

import subprocess
from pathlib import Path
import docx
import matplotlib.image as mpimg
import matplotlib.pyplot as plt
import pandas as pd
import pypdf
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn
from docx.shared import Inches, Pt, RGBColor

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


def set_cell_margins(cell, top=70, bottom=70, left=110, right=110):
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = OxmlElement('w:tcMar')
    for m, val in [('top', top), ('bottom', bottom), ('left', left), ('right', right)]:
        node = OxmlElement(f'w:{m}')
        node.set(qn('w:w'), str(val))
        node.set(qn('w:type'), 'dxa')
        tcMar.append(node)
    tcPr.append(tcMar)


def generate_combined_ab_figure() -> Path:
    """Genera panel combinado de métricas y matrices de confusión para ajuste de 5 páginas."""
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    out_path = FIGURES_DIR / "ab_test_combined_panel.png"

    img_bars = mpimg.imread(str(FIGURES_DIR / "ab_test_metrics_comparison.png"))
    img_cm = mpimg.imread(str(FIGURES_DIR / "ab_test_confusion_matrices.png"))

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8.5), dpi=300)
    ax1.imshow(img_bars)
    ax1.axis('off')
    ax2.imshow(img_cm)
    ax2.axis('off')

    plt.tight_layout()
    fig.savefig(str(out_path), dpi=300, bbox_inches='tight')
    plt.close(fig)
    print(f"✓ Panel combinado A/B generado en: {out_path}")
    return out_path


def build_docx_report() -> Path:
    doc = docx.Document()

    for section in doc.sections:
        section.top_margin = Inches(0.8)
        section.bottom_margin = Inches(0.8)
        section.left_margin = Inches(0.8)
        section.right_margin = Inches(0.8)

    normal_style = doc.styles['Normal']
    normal_style.font.name = 'Arial'
    normal_style.font.size = Pt(10.5)
    normal_style.font.color.rgb = GRIS_TEXTO
    normal_style.paragraph_format.line_spacing = 1.15
    normal_style.paragraph_format.space_after = Pt(4)

    # 1. ENCABEZADO INSTITUCIONAL
    p_inst = doc.add_paragraph()
    p_inst.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_inst = p_inst.add_run("TECNOLÓGICO DE MONTERREY\nMAESTRÍA EN INTELIGENCIA ARTIFICIAL APLICADA")
    r_inst.font.name = 'Arial'
    r_inst.font.size = Pt(12)
    r_inst.font.bold = True
    r_inst.font.color.rgb = AZUL_TEC

    p_sub = doc.add_paragraph()
    p_sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_sub = p_sub.add_run("TC5061 — Operaciones de Inteligencia Artificial (MLOps)\nEntregable 8: Monitoreo y Reporte de Drift en el Proyecto & A/B Testing")
    r_sub.font.name = 'Arial'
    r_sub.font.size = Pt(10)
    r_sub.font.color.rgb = RGBColor(100, 116, 139)

    p_line = doc.add_paragraph()
    p_line.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_line = p_line.add_run("―" * 58)
    r_line.font.color.rgb = RGBColor(203, 213, 225)

    p_title = doc.add_paragraph()
    p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_title = p_title.add_run("Reporte Técnico y Ejecutivo: Monitoreo de Data Drift con Evidently y Evaluación A/B de Versiones en MLflow")
    r_title.font.name = 'Arial'
    r_title.font.size = Pt(15)
    r_title.font.bold = True
    r_title.font.color.rgb = AZUL_TEC

    # 2. METADATOS Y EQUIPO
    table_meta = doc.add_table(rows=4, cols=2)
    table_meta.alignment = WD_TABLE_ALIGNMENT.CENTER
    meta_data = [
        ("Proyecto / Sistema:", "Plataforma MLOps MiBici Guadalajara (Modelo P2: Riesgo Operativo a 2 Horas)"),
        ("Repositorio GitHub Oficial:", "https://github.com/Diegob059/TC5061-Proyecto-Equipo30"),
        ("Modelos en Model Registry:", "mibici-equipo30-p2-riesgo | Versión 1 (@champion) vs. Versión 2 (@challenger)"),
        ("Fecha de Entrega:", "15 de Noviembre de 2026 — Equipo 30"),
    ]
    for i, (k, v) in enumerate(meta_data):
        row = table_meta.rows[i]
        c0, c1 = row.cells[0], row.cells[1]
        c0.width, c1.width = Inches(2.2), Inches(4.5)
        c0.text, c1.text = k, v
        c0.paragraphs[0].runs[0].font.bold = True
        c0.paragraphs[0].runs[0].font.size = Pt(9)
        c1.paragraphs[0].runs[0].font.size = Pt(9)
        set_cell_background(c0, GRIS_CLARO)
        set_cell_background(c1, "FFFFFF")
        set_cell_margins(c0, 40, 40, 80, 80)
        set_cell_margins(c1, 40, 40, 80, 80)

    doc.add_paragraph()

    p_t = doc.add_paragraph()
    r_t = p_t.add_run("Integrantes del Equipo 30:")
    r_t.font.bold = True
    r_t.font.size = Pt(10)
    r_t.font.color.rgb = AZUL_TEC

    table_team = doc.add_table(rows=5, cols=3)
    table_team.alignment = WD_TABLE_ALIGNMENT.CENTER
    headers = ["Nombre del Integrante", "Matrícula", "Contribución en la Entrega 8"]
    for j, h in enumerate(headers):
        c = table_team.rows[0].cells[j]
        c.text = h
        c.paragraphs[0].runs[0].font.bold = True
        c.paragraphs[0].runs[0].font.size = Pt(9)
        c.paragraphs[0].runs[0].font.color.rgb = RGBColor(255, 255, 255)
        set_cell_background(c, "003366")
        set_cell_margins(c, 50, 50, 80, 80)

    team_data = [
        ("Ricardo Bahamón", "A01840023", "MLOps Lead: Model Registry v2, pipeline A/B testing, contrastes estadísticos y reporte"),
        ("Diego Becerril", "A01748115", "Lead Data Scientist: Configuración de Evidently AI, análisis de data drift y visualizaciones"),
        ("Gregorio Escobedo Straffon", "A01840612", "Data Engineer: Muestreo estratificado de producción 2026, validación de esquemas y tests"),
        ("Freddin Alcántara", "A01797741", "Product & Operations Lead: Criterios operativos CCO, formulación de umbrales y gobernanza CT"),
    ]
    for i, row_data in enumerate(team_data, start=1):
        row = table_team.rows[i]
        for j, val in enumerate(row_data):
            c = row.cells[j]
            c.text = val
            c.paragraphs[0].runs[0].font.size = Pt(8.5)
            set_cell_background(c, GRIS_CLARO if i % 2 == 1 else "FFFFFF")
            set_cell_margins(c, 40, 40, 80, 80)

    doc.add_paragraph()

    # 3. SECCIÓN 1: INTRODUCCIÓN Y METODOLOGÍA DE DATOS
    p_s1 = doc.add_paragraph()
    r_s1 = p_s1.add_run("1. Metodología y Definición de Conjuntos de Datos")
    r_s1.font.size = Pt(12)
    r_s1.font.bold = True
    r_s1.font.color.rgb = AZUL_TEC

    doc.add_paragraph(
        "En sistemas de aprendizaje automático desplegados en producción, el desempeño del modelo no es estático: "
        "la dinámica urbana, estacionalidades y cambios de hábitos introducen perturbaciones en la distribución de entrada "
        "(data drift) y en las relaciones funcionales (concept drift). El presente trabajo añade al proyecto "
        "MiBici Guadalajara la capa de observabilidad continua y experimentación controlada (Entregable 8). "
        "Se evalúa el modelo multiclase de riesgo operativo a 2 horas (Pregunta 2: Normal = 0, Desabasto = 1, Saturación = 2)."
    )

    doc.add_paragraph(
        "Para simular un entorno de producción fidedigno y auditable, se establecieron dos ventanas temporales rigurosas "
        "con base en los datos abiertos oficiales de MiBici (https://mibici.net/es/datos-abiertos/):"
    )

    p_b1 = doc.add_paragraph(style='List Bullet')
    p_b1.add_run("Conjunto de Referencia (Baseline 2025): ").font.bold = True
    p_b1.add_run(
        "Periodo histórico desde el 01/01/2025 hasta el 31/12/2025 (timestamp < 2025-12-31 22:00:00). "
        "Contiene 4,037,300 registros horarios y representa el régimen basal bajo el cual se entrenó el Champion actual. "
        "Para auditoría se extrajo una muestra estratificada reproducible de 7,500 observaciones."
    )

    p_b2 = doc.add_paragraph(style='List Bullet')
    p_b2.add_run("Conjunto Actual (Producción 2026): ").font.bold = True
    p_b2.add_run(
        "Periodo posterior continuo disponible desde el 01/01/2026 hasta el 30/09/2026 (timestamp >= 2026-01-01 00:00:00), "
        "con 3,078,500 registros horarios. Representa el flujo real de datos en servicio en un nuevo ciclo anual. "
        "Se muestrearon 7,500 observaciones para el análisis de drift y 50,000 para la suite de A/B testing."
    )

    # 4. SECCIÓN 2: REPORTE DE DATA DRIFT CON EVIDENTLY
    p_s2 = doc.add_paragraph()
    r_s2 = p_s2.add_run("2. Monitoreo y Auditoría de Data Drift con Evidently AI")
    r_s2.font.size = Pt(12)
    r_s2.font.bold = True
    r_s2.font.color.rgb = AZUL_TEC

    doc.add_paragraph(
        "Se integró Evidently AI (evidently==0.7.23) para contrastar las distribuciones empíricas de las 17 variables predictoras. "
        "Se aplicó la distancia Wasserstein normalizada para variables continuas y la divergencia Jensen-Shannon para discretas, "
        "fijando el umbral crítico en 0.10 y una alerta temprana en 0.05."
    )

    fig_summary = FIGURES_DIR / "evidently_drift_summary_card.png"
    if fig_summary.exists():
        p_img = doc.add_paragraph()
        p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_img.add_run().add_picture(str(fig_summary), width=Inches(5.5))

    fig_ranking = FIGURES_DIR / "evidently_drift_wasserstein_ranking.png"
    if fig_ranking.exists():
        p_img2 = doc.add_paragraph()
        p_img2.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_img2.add_run().add_picture(str(fig_ranking), width=Inches(5.5))

    # 5. SECCIÓN 3: INTERPRETACIÓN DEL DRIFT Y CONSECUENCIAS OPERATIVAS
    p_s3 = doc.add_paragraph()
    r_s3 = p_s3.add_run("3. Interpretación Técnica de Variables Afectadas e Implicaciones de Negocio")
    r_s3.font.size = Pt(12)
    r_s3.font.bold = True
    r_s3.font.color.rgb = AZUL_TEC

    doc.add_paragraph(
        "El dictamen global de Evidently reporta 0.0% de dataset drift crítico: ninguna característica excedió el umbral "
        "de 0.10. Asimismo, la calidad de datos es del 100% (cero valores nulos, infinitos o no tipificados). Sin embargo, "
        "el análisis granular evidencia un gradiente de desplazamiento focalizado en variables de balance rodante y flujos semanales:"
    )

    doc.add_paragraph(
        "• Balance Rodante de 12 y 3 Horas (balance_rolling_12h: 0.0711, balance_rolling_3h: 0.0646): Son las variables con "
        "mayor desplazamiento relativo. Miden la acumulación neta de bicicletas (llegadas - salidas). A inicios de 2026 se "
        "observó una intensificación de la asimetría pendular en horas pico (estaciones laborales receptoras que se llenan "
        "más rápidamente y colonias habitacionales con vaciados más acelerados). Esto ensancha las colas de la distribución empírica."
    )

    doc.add_paragraph(
        "• Lags Semanales (llegadas_lag_168: 0.0527, salidas_lag_168: 0.0391): El desfase entre semanas calendario de 2025 "
        "y 2026 genera pequeñas variaciones en el ciclo de 7 días, especialmente tras periodos vacacionales."
    )

    doc.add_paragraph(
        "• Invarianza de Infraestructura y Calendario: Variables geográficas (latitude: 0.033, longitude: 0.015), capacidad física "
        "(capacity: 0.013) y componentes cíclicos horarios (sin/cos_hour: <0.013) se mantienen prácticamente idénticas, lo que confirma "
        "que la red física de estaciones no ha sufrido alteraciones estructurales."
    )

    doc.add_paragraph(
        "Implicaciones Operativas: En el Centro de Control de Operaciones (CCO), un sesgo en las variables de balance acumulado "
        "representa el riesgo de que el modelo comience a descalibrar las probabilidades predichas, subestimando desabastos en horas "
        "críticas o generando falsas alarmas de saturación. Esto motiva la necesidad de entrenar un modelo alternativo (Challenger) "
        "con regularización reforzada y someter ambas versiones a una prueba A/B en producción."
    )

    fig_dist = FIGURES_DIR / "evidently_distributions_drift.png"
    if fig_dist.exists():
        p_img3 = doc.add_paragraph()
        p_img3.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_img3.add_run().add_picture(str(fig_dist), width=Inches(5.5))

    # 6. SECCIÓN 4: MODELO ALTERNATIVO Y A/B TESTING
    p_s4 = doc.add_paragraph()
    r_s4 = p_s4.add_run("4. Versión Alternativa (Challenger) y Resultados del A/B Testing")
    r_s4.font.size = Pt(12)
    r_s4.font.bold = True
    r_s4.font.color.rgb = AZUL_TEC

    doc.add_paragraph(
        "Para responder a la deriva detectada, se entrenó la Versión 2 (Challenger: lgbm_challenger_v2) incorporando: "
        "regularización L1/L2 (reg_alpha=0.1, reg_lambda=0.5), submuestreo de características (colsample_bytree=0.80) para "
        "mitigar la dependencia de balances rodantes, bagging (subsample=0.85) y profundidad acotada (depth=7, leaves=40). "
        "Esta versión se registró formalmente en el Model Registry de MLflow como Versión 2 con alias @challenger, manteniendo "
        "la Versión 1 como @champion."
    )

    doc.add_paragraph(
        "Ambos modelos fueron evaluados sobre una muestra estratificada de 50,000 registros del periodo actual (Año 2026). "
        "La Tabla 1 resume el contraste de métricas obtenido:"
    )

    table_ab = doc.add_table(rows=10, cols=5)
    table_ab.alignment = WD_TABLE_ALIGNMENT.CENTER
    ab_headers = ["Métrica Operativa Clave", "Versión 1 (@champion)", "Versión 2 (@challenger)", "Delta Absoluto", "Delta %"]
    for j, h in enumerate(ab_headers):
        c = table_ab.rows[0].cells[j]
        c.text = h
        c.paragraphs[0].runs[0].font.bold = True
        c.paragraphs[0].runs[0].font.size = Pt(8.5)
        c.paragraphs[0].runs[0].font.color.rgb = RGBColor(255, 255, 255)
        set_cell_background(c, "003366")
        set_cell_margins(c, 40, 40, 60, 60)

    rows_data = [
        ("Balanced Accuracy", "0.8796", "0.8756", "-0.0041", "-0.46%"),
        ("Macro F1-Score", "0.3704", "0.3663", "-0.0041", "-1.11%"),
        ("Weighted F1-Score", "0.9087", "0.9045", "-0.0041", "-0.45%"),
        ("Recall Desabasto (Clase 1 - Crítica)", "0.8808", "0.8756", "-0.0052", "-0.59%"),
        ("Precisión Desabasto (Clase 1)", "0.0440", "0.0425", "-0.0014", "-3.22%"),
        ("F2-Score Desabasto (Clase 1)", "0.1832", "0.1781", "-0.0051", "-2.79%"),
        ("Recall Saturación (Clase 2)", "0.9121", "0.9121", "0.0000", "0.00%"),
        ("Precisión Saturación (Clase 2)", "0.0592", "0.0560", "-0.0032", "-5.39%"),
        ("Latencia Inferencia (ms / 1k)", "4.23 ms", "3.50 ms", "-0.73 ms", "-17.30%"),
    ]

    for i, r_data in enumerate(rows_data):
        row = table_ab.rows[i + 1]
        for j, val in enumerate(r_data):
            cell = row.cells[j]
            cell.text = val
            cell.paragraphs[0].runs[0].font.size = Pt(8)
            set_cell_background(cell, GRIS_CLARO if i % 2 == 1 else "FFFFFF")
            set_cell_margins(cell, 30, 30, 50, 50)

    doc.add_paragraph()

    fig_ab_panel = FIGURES_DIR / "ab_test_combined_panel.png"
    if fig_ab_panel.exists():
        p_img4 = doc.add_paragraph()
        p_img4.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_img4.add_run().add_picture(str(fig_ab_panel), width=Inches(5.5))

    doc.add_paragraph(
        "Contraste Estadístico: La prueba de McNemar confirmó que la divergencia en errores es estadísticamente significativa "
        "(chi-cuadrado = 151.73, p < 0.001). El análisis bootstrap al 95% de confianza (400 réplicas) para la diferencia de Macro F1 "
        "arrojó un intervalo de [-0.0051, -0.0031], confirmando que el Champion v1 conserva superioridad en balance multiclase."
    )

    # 7. SECCIÓN 5: RECOMENDACIÓN DE CONTINUOUS TRAINING
    p_s5 = doc.add_paragraph()
    r_s5 = p_s5.add_run("5. Decisión de Versión y Recomendación de Continuous Training (CT)")
    r_s5.font.size = Pt(12)
    r_s5.font.bold = True
    r_s5.font.color.rgb = AZUL_TEC

    doc.add_paragraph(
        "Decisión del A/B Testing: Se determina conservar formalmente la Versión 1 (lgbm_profundo) con el alias de producción @champion. "
        "La justificación técnica y de negocio radica en que el Champion sostiene un Recall en Desabasto superior (88.08% vs. 87.56%) "
        "y un Macro F1 superior (0.3704 vs. 0.3663). En la operación de MiBici, el desabasto representa la falla de servicio más crítica "
        "(el usuario llega a la estación y no encuentra bicicleta para trasladarse), por lo que sacrificar medio punto porcentual de recall "
        "a cambio de menor latencia (3.5 ms vs. 4.2 ms) no está justificado operativamente."
    )

    doc.add_paragraph(
        "Estrategia de Continuous Training (CT) Propuesta: Para garantizar la vigencia del modelo a largo plazo, se define la siguiente arquitectura:"
    )

    p_ct1 = doc.add_paragraph(style='List Bullet')
    p_ct1.add_run("Disparadores Basados en Drift (Evidently AI): ").font.bold = True
    p_ct1.add_run("Auditoría semanal programada. Si balance_rolling_12h excede 0.10 o más del 25% de variables superan 0.08, se gatilla el reentrenamiento automático.")

    p_ct2 = doc.add_paragraph(style='List Bullet')
    p_ct2.add_run("Disparadores de Rendimiento Operativo: ").font.bold = True
    p_ct2.add_run("Si el Recall en Desabasto a 14 días cae de 85.0% o el Macro F1 de 0.35, se activa reentrenamiento correctivo.")

    p_ct3 = doc.add_paragraph(style='List Bullet')
    p_ct3.add_run("Ventana Temporal y Regularización Híbrida: ").font.bold = True
    p_ct3.add_run("Ventana rodante de 12 meses con ponderación temporal decrescente, incorporando la regularización L1/L2 y colsample=0.80 explorados en el Challenger v2.")

    p_ct4 = doc.add_paragraph(style='List Bullet')
    p_ct4.add_run("Salvaguardas de Despliegue: ").font.bold = True
    p_ct4.add_run("Ningún modelo generado por CT sustituirá al Champion sin validar cero errores de esquema, latencia < 10 ms y paridad estadística en Recall de Desabasto en un A/B test canario de 72 horas.")

    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    docx_path = DOCS_DIR / "TC5061_Drift_ABTest_Equipo30.docx"
    doc.save(docx_path)
    print(f"✓ Documento DOCX guardado en: {docx_path}")
    return docx_path


def build_markdown_report() -> Path:
    md_content = r"""# TECNOLÓGICO DE MONTERREY
## Maestría en Inteligencia Artificial Aplicada
### TC5061 — Operaciones de Inteligencia Artificial (MLOps)
**Entregable 8: Monitoreo y Reporte de Drift en el Proyecto & A/B Testing**

---

# Reporte Técnico y Ejecutivo: Monitoreo de Data Drift con Evidently y Evaluación A/B de Versiones en MLflow

## Metadatos del Proyecto

| Campo | Valor |
| :--- | :--- |
| **Proyecto / Sistema:** | Plataforma MLOps MiBici Guadalajara (Modelo P2: Riesgo Operativo a 2 Horas) |
| **Repositorio Oficial GitHub:** | [https://github.com/Diegob059/TC5061-Proyecto-Equipo30](https://github.com/Diegob059/TC5061-Proyecto-Equipo30) |
| **Modelos Evaluados:** | `mibici-equipo30-p2-riesgo` | Versión 1 (`@champion`) vs. Versión 2 (`@challenger`) |
| **Fecha de Entrega:** | 15 de Noviembre de 2026 — Equipo 30 |

## 1. Integrantes del Equipo (Equipo 30)

| Nombre del Integrante | Matrícula | Contribución en la Entrega 8 |
| :--- | :--- | :--- |
| **Ricardo Bahamón** | A01840023 | MLOps Lead: Model Registry v2, pipeline A/B testing, contrastes estadísticos y reporte |
| **Diego Becerril** | A01748115 | Lead Data Scientist: Configuración de Evidently AI, análisis de data drift y visualizaciones |
| **Gregorio Escobedo Straffon** | A01840612 | Data Engineer: Muestreo estratificado de producción 2026, validación de esquemas y tests |
| **Freddin Alcántara** | A01797741 | Product & Operations Lead: Criterios operativos CCO, formulación de umbrales y gobernanza CT |

---

## 1. Metodología y Definición de Conjuntos de Datos

En sistemas de aprendizaje automático en producción, el desempeño no es estático: la dinámica de movilidad urbana y las variaciones temporales introducen perturbaciones en las distribuciones de entrada (*data drift*) y en las relaciones funcionales (*concept drift*). En este entregable, el Equipo 30 dota a la plataforma MiBici de capacidades de observabilidad continua y experimentación controlada. Evaluamos el modelo multiclase de riesgo operativo a 2 horas (**Pregunta 2**: `0: Normal`, `1: Desabasto`, `2: Saturación`).

Para garantizar validez ecológica y reproducibilidad estricta sin fuga temporal (*anti-leakage*), se definieron dos ventanas basadas en los [datos abiertos de MiBici](https://mibici.net/es/datos-abiertos/):

* **Conjunto de Referencia (Baseline 2025):** Registros horarios desde `2025-01-01` hasta `2025-12-31 22:00:00` (4,037,300 filas totales). Representa el régimen operativo basal bajo el cual se entrenó la versión actual de producción (**Versión 1 Champion: `lgbm_profundo`**). Para la auditoría de drift se utilizó una muestra estratificada representativa de 7,500 observaciones.
* **Conjunto Actual (Producción 2026):** Registros horarios desde `2026-01-01 00:00:00` hasta `2026-09-30` (3,078,500 filas totales). Representa el comportamiento real del sistema en un ciclo anual posterior no visto durante el entrenamiento. Se utilizaron 7,500 observaciones para drift y 50,000 para el A/B testing.

---

## 2. Monitoreo y Auditoría de Data Drift con Evidently AI

Se implementó el pipeline de monitoreo continuo utilizando la versión actual de Evidently AI (`evidently==0.7.23`). Se ejecutaron simultáneamente `DataDriftPreset` y `DataSummaryPreset` sobre las **17 variables predictoras**. Se aplicó la distancia Wasserstein normalizada para variables continuas y la divergencia Jensen-Shannon para variables discretas, con un umbral crítico de $0.10$ y un umbral de advertencia temprana de $0.05$.

![Auditoría Ejecutiva de Data Drift y Calidad de Datos (Evidently)](reports/figures/evidently_drift_summary_card.png){width=48%}

![Ranking de Deriva Estadística por Variable en P2](reports/figures/evidently_drift_wasserstein_ranking.png){width=48%}

---

## 3. Interpretación Técnica de Variables y Consecuencias de Negocio

El dictamen global de Evidently confirma **0.0% de dataset drift crítico** (0 de 17 variables superaron el umbral de 0.10) y **100% de calidad de datos** (cero valores nulos, infinitos o fuera de esquema). No obstante, el ranking revela un gradiente de deriva concentrado en variables dinámicas:

1. **Balance Rodante de 12h y 3h (`balance_rolling_12h`: 0.0711, `balance_rolling_3h`: 0.0646):** Son las variables con mayor desplazamiento relativo del sistema. Miden el diferencial neto acumulado de bicicletas (llegadas menos salidas). A inicios de 2026, la reactivación laboral y académica intensificó la asimetría de viajes entre zonas residenciales y corredores corporativos/universitarios, ensanchando las colas de la distribución empírica.
2. **Lags Semanales (`llegadas_lag_168`: 0.0527, `salidas_lag_168`: 0.0391):** Reflejan ligeras divergencias por el calendario de festividades y retorno escolar de inicio de año respecto a 2025.
3. **Invarianza Física y Geográfica:** La capacidad instalada (`capacity`: 0.013) y coordenadas (`latitude`: 0.033, `longitude`: 0.015) permanecen prácticamente invariantes, certificando que la topología de estaciones no sufrió reconfiguraciones drásticas.

**Implicaciones Operativas:** En el Centro de Control de Operaciones (CCO), un sesgo en los balances acumulados puede inducir descalibración en los umbrales de probabilidad del estimador, aumentando los falsos negativos en desabasto. Esto justificó diseñar una versión alternativa con regularización reforzada.

![Comparación de Densidades Empíricas (KDE) entre 2025 y 2026](reports/figures/evidently_distributions_drift.png){width=48%}

---

## 4. Versión Alternativa (Challenger) y Resultados del A/B Testing

Ante la deriva observada, se diseñó y entrenó la **Versión 2 (Challenger: `lgbm_challenger_v2`)** incorporando: regularización L1/L2 (`reg_alpha=0.1`, `reg_lambda=0.5`), submuestreo de características (`colsample_bytree=0.80`) para evitar la dependencia excesiva de los balances rodantes, bagging (`subsample=0.85`) y menor profundidad (`depth=7`, `leaves=40`). Esta versión se registró formalmente en el Model Registry de MLflow como Versión 2 con el alias `@challenger`, manteniendo la Versión 1 como `@champion`.

Ambas versiones se evaluaron sobre 50,000 registros estratificados de producción 2026:

| Métrica Operativa Clave | Versión 1 (@champion) | Versión 2 (@challenger) | Delta Absoluto | Delta % |
| :--- | :---: | :---: | :---: | :---: |
| **Balanced Accuracy** | 0.8796 | 0.8756 | -0.0041 | -0.46% |
| **Macro F1-Score** | 0.3704 | 0.3663 | -0.0041 | -1.11% |
| **Weighted F1-Score** | 0.9087 | 0.9045 | -0.0041 | -0.45% |
| **Recall Desabasto (Clase 1 - Crítica)** | **0.8808** | **0.8756** | **-0.0052** | **-0.59%** |
| **Precisión Desabasto (Clase 1)** | 0.0440 | 0.0425 | -0.0014 | -3.22% |
| **F2-Score Desabasto (Clase 1)** | 0.1832 | 0.1781 | -0.0051 | -2.79% |
| **Recall Saturación (Clase 2)** | 0.9121 | 0.9121 | 0.0000 | 0.00% |
| **Precisión Saturación (Clase 2)** | 0.0592 | 0.0560 | -0.0032 | -5.39% |
| **Latencia Inferencia (ms / 1k)** | **4.23 ms** | **3.50 ms** | **-0.73 ms** | **-17.30%** |

![Resultados Integrales del A/B Testing: Comparación de Métricas y Matrices de Confusión (Champion v1 vs. Challenger v2)](reports/figures/ab_test_combined_panel.png){width=48%}

**Inferencia Estadística:** La prueba de McNemar confirmó que la divergencia en errores es estadísticamente significativa ($\chi^2 = 151.73$, $p < 0.001$). El análisis bootstrap al 95% de confianza (400 réplicas) para $\Delta \text{Macro F1}$ arrojó un intervalo $[-0.0051, -0.0031]$, confirmando que el Champion v1 conserva una superioridad sistemática en balance multiclase.

---

## 5. Decisión de Versión y Recomendación de Continuous Training (CT)

**Decisión del A/B Testing:** Se determina **mantener la Versión 1 (`lgbm_profundo`) como `@champion` activo en producción**. La justificación de negocio es contundente: el Champion logra mayor Recall en Desabasto (88.08% vs. 87.56%) y mayor Macro F1 (0.3704 vs. 0.3663). En MiBici, la insatisfacción por desabasto (no poder tomar bicicleta) es el evento de mayor fricción operativa; reducir medio punto porcentual de recall a cambio de menor latencia (3.5 ms vs. 4.2 ms) sería perjudicial para el usuario final.

**Estrategia de Continuous Training (CT) Recomendada:**
1. **Disparadores de Drift (Evidently):** Auditoría semanal programada. Si `balance_rolling_12h` excede $0.10$ o más del 25% de variables superan $0.08$, se gatilla el reentrenamiento automático.
2. **Disparadores de Desempeño:** Si el Recall en Desabasto a 14 días cae de 85.0% o el Macro F1 de 0.35, se activa reentrenamiento correctivo.
3. **Esquema de Reentrenamiento:** Ventana rodante de 12 meses con ponderación temporal decrescente, incorporando la regularización L1/L2 y `colsample_bytree=0.80` validadas en el Challenger.
4. **Gateways de Despliegue:** Ningún modelo generado por CT sustituirá al Champion sin validar cero errores de esquema, latencia < 10 ms y paridad estadística en Recall de Desabasto en un A/B test canario de 72 horas.
"""

    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    md_path = DOCS_DIR / "TC5061_Drift_ABTest_Equipo30.md"
    md_path.write_text(md_content, encoding="utf-8")
    print(f"✓ Documento Markdown guardado en: {md_path}")
    return md_path


def compile_pdf_report(md_path: Path) -> Path:
    pdf_path = DOCS_DIR / "TC5061_Drift_ABTest_Equipo30.pdf"

    cmd = [
        "pandoc",
        str(md_path),
        "-f", "markdown-implicit_figures",
        "-o",
        str(pdf_path),
        "--pdf-engine=xelatex",
        "-V", "geometry:margin=0.7in",
        "-V", "mainfont=Helvetica",
        "-V", "fontsize=10pt",
        "-V", "colorlinks=true",
        "-V", "linkcolor=blue",
        "-V", "urlcolor=blue",
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode == 0 and pdf_path.exists():
        reader = pypdf.PdfReader(str(pdf_path))
        num_pages = len(reader.pages)
        print(f"✓ Documento PDF compilado con xelatex en: {pdf_path} ({num_pages} páginas)")
    else:
        print(f"Aviso al compilar con xelatex: {res.stderr}")

    return pdf_path


def main():
    generate_combined_ab_figure()
    docx_file = build_docx_report()
    md_file = build_markdown_report()
    pdf_file = compile_pdf_report(md_file)


if __name__ == "__main__":
    main()
