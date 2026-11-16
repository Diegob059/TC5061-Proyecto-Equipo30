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


def set_cell_margins(cell, top=80, bottom=80, left=120, right=120):
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = OxmlElement('w:tcMar')
    for m, val in [('top', top), ('bottom', bottom), ('left', left), ('right', right)]:
        node = OxmlElement(f'w:{m}')
        node.set(qn('w:w'), str(val))
        node.set(qn('w:type'), 'dxa')
        tcMar.append(node)
    tcPr.append(tcMar)


def set_cell_border(cell, **kwargs):
    """Configura bordes XML de celda (val, sz, space, color)."""
    tcPr = cell._tc.get_or_add_tcPr()
    tcBorders = parse_xml(
        f'<w:tcBorders {nsdecls("w")}>\n'
        f'  <w:top w:val="{kwargs.get("top", {}).get("val", "none")}" w:sz="{kwargs.get("top", {}).get("sz", "4")}" w:space="0" w:color="{kwargs.get("top", {}).get("color", "auto")}"/>\n'
        f'  <w:left w:val="{kwargs.get("left", {}).get("val", "none")}" w:sz="{kwargs.get("left", {}).get("sz", "4")}" w:space="0" w:color="{kwargs.get("left", {}).get("color", "auto")}"/>\n'
        f'  <w:bottom w:val="{kwargs.get("bottom", {}).get("val", "none")}" w:sz="{kwargs.get("bottom", {}).get("sz", "4")}" w:space="0" w:color="{kwargs.get("bottom", {}).get("color", "auto")}"/>\n'
        f'  <w:right w:val="{kwargs.get("right", {}).get("val", "none")}" w:sz="{kwargs.get("right", {}).get("sz", "4")}" w:space="0" w:color="{kwargs.get("right", {}).get("color", "auto")}"/>\n'
        f'</w:tcBorders>'
    )
    tcPr.append(tcBorders)


def add_callout(doc, title: str, text: str, bg_hex="F0F9FF", border_hex="003366"):
    """Inserta una caja de llamada/resumen ejecutivo con borde izquierdo grueso."""
    table = doc.add_table(rows=1, cols=1)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    cell = table.cell(0, 0)
    cell.width = Inches(6.8)
    set_cell_background(cell, bg_hex)
    set_cell_margins(cell, top=100, bottom=100, left=160, right=140)

    tcPr = cell._tc.get_or_add_tcPr()
    borders = parse_xml(
        f'<w:tcBorders {nsdecls("w")}>\n'
        f'  <w:top w:val="none"/>\n'
        f'  <w:left w:val="single" w:sz="24" w:space="0" w:color="{border_hex}"/>\n'
        f'  <w:bottom w:val="none"/>\n'
        f'  <w:right w:val="none"/>\n'
        f'</w:tcBorders>'
    )
    tcPr.append(borders)

    p = cell.paragraphs[0]
    p.paragraph_format.line_spacing = 1.15
    p.paragraph_format.space_after = Pt(2)
    r_title = p.add_run(f"📌 {title}\n")
    r_title.font.name = 'Arial'
    r_title.font.size = Pt(10)
    r_title.font.bold = True
    r_title.font.color.rgb = AZUL_TEC

    r_text = p.add_run(text)
    r_text.font.name = 'Arial'
    r_text.font.size = Pt(9.5)
    r_text.font.color.rgb = GRIS_TEXTO

    p_spacer = doc.add_paragraph()
    p_spacer.paragraph_format.space_before = Pt(0)
    p_spacer.paragraph_format.space_after = Pt(2)


def add_figure_with_caption(doc, img_path: Path, caption: str, width=Inches(5.7)):
    """Inserta imagen centrada con su pie de figura formal."""
    if not img_path.exists():
        return
    p_img = doc.add_paragraph()
    p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_img.paragraph_format.space_before = Pt(6)
    p_img.paragraph_format.space_after = Pt(2)
    p_img.add_run().add_picture(str(img_path), width=width)

    p_cap = doc.add_paragraph()
    p_cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_cap.paragraph_format.space_before = Pt(0)
    p_cap.paragraph_format.space_after = Pt(6)
    r_cap = p_cap.add_run(caption)
    r_cap.font.name = 'Arial'
    r_cap.font.size = Pt(9)
    r_cap.font.italic = True
    r_cap.font.color.rgb = RGBColor(100, 116, 139)


def add_custom_heading(doc, text: str, level: int = 1):
    h = doc.add_heading(text, level=level)
    h.paragraph_format.keep_with_next = True
    h.paragraph_format.space_before = Pt(14 if level == 1 else 9)
    h.paragraph_format.space_after = Pt(3)
    for run in h.runs:
        run.font.name = 'Arial'
        run.font.bold = True
        if level == 1:
            run.font.size = Pt(13)
            run.font.color.rgb = AZUL_TEC
        else:
            run.font.size = Pt(11)
            run.font.color.rgb = AZUL_TEC
    return h


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

        # Header institucional
        header = section.header
        p_head = header.paragraphs[0]
        p_head.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        r_head = p_head.add_run("TECNOLÓGICO DE MONTERREY — MIAA  |  TC5061: MLOps")
        r_head.font.name = 'Arial'
        r_head.font.size = Pt(8.5)
        r_head.font.color.rgb = RGBColor(148, 163, 184)

        # Footer con paginación dinámica XML
        footer = section.footer
        p_foot = footer.paragraphs[0]
        p_foot.alignment = WD_ALIGN_PARAGRAPH.LEFT
        r_fl = p_foot.add_run("TC5061 Entregable 8: Monitoreo y Drift & A/B Testing  |  Equipo 30\t")
        r_fl.font.name = 'Arial'
        r_fl.font.size = Pt(8.5)
        r_fl.font.color.rgb = RGBColor(148, 163, 184)

        r_p1 = p_foot.add_run("Página ")
        r_p1.font.name = 'Arial'
        r_p1.font.size = Pt(8.5)
        r_p1.font.color.rgb = RGBColor(100, 116, 139)
        fld1 = parse_xml(r'<w:fldChar %s w:fldCharType="begin"/>' % nsdecls('w'))
        instr1 = parse_xml(r'<w:instrText %s xml:space="preserve"> PAGE </w:instrText>' % nsdecls('w'))
        fld2 = parse_xml(r'<w:fldChar %s w:fldCharType="separate"/>' % nsdecls('w'))
        fld3 = parse_xml(r'<w:fldChar %s w:fldCharType="end"/>' % nsdecls('w'))
        r_p1._r.extend([fld1, instr1, fld2, fld3])

        r_p2 = p_foot.add_run(" de ")
        r_p2.font.name = 'Arial'
        r_p2.font.size = Pt(8.5)
        r_p2.font.color.rgb = RGBColor(100, 116, 139)
        fld4 = parse_xml(r'<w:fldChar %s w:fldCharType="begin"/>' % nsdecls('w'))
        instr2 = parse_xml(r'<w:instrText %s xml:space="preserve"> NUMPAGES </w:instrText>' % nsdecls('w'))
        fld5 = parse_xml(r'<w:fldChar %s w:fldCharType="separate"/>' % nsdecls('w'))
        fld6 = parse_xml(r'<w:fldChar %s w:fldCharType="end"/>' % nsdecls('w'))
        r_p2._r.extend([fld4, instr2, fld5, fld6])

    normal_style = doc.styles['Normal']
    normal_style.font.name = 'Arial'
    normal_style.font.size = Pt(11)
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
        c0.width, c1.width = Inches(2.2), Inches(4.6)
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
    add_custom_heading(doc, "1. Metodología y Definición de Conjuntos de Datos", level=1)

    doc.add_paragraph(
        "En sistemas de aprendizaje automático desplegados en entornos de producción, el desempeño predictivo "
        "no permanece estático a lo largo del tiempo. Las transformaciones de movilidad urbana, las variaciones "
        "meteorológicas, las fluctuaciones demográficas y los cambios estacionales introducen perturbaciones tanto en la "
        "distribución marginal de las características de entrada (data drift o covariate shift) como en la relación condicional "
        "entre los predictores y la variable objetivo (concept drift). El presente trabajo añade formalmente al proyecto "
        "MiBici Guadalajara la capa de observabilidad continua y experimentación controlada (Entregable 8). "
        "El objeto central de análisis es el modelo multiclase de riesgo operativo a 2 horas (Pregunta 2: 0: Normal, 1: Desabasto, 2: Saturación)."
    )

    doc.add_paragraph(
        "Para simular un entorno de producción fidedigno y auditable sin incurrir en fuga temporal (leakage), "
        "se definieron dos ventanas temporales rigurosas a partir del portal de datos abiertos oficial de MiBici (https://mibici.net/es/datos-abiertos/):"
    )

    p_b1 = doc.add_paragraph(style='List Bullet')
    p_b1.add_run("Conjunto de Referencia (Baseline 2025): ").font.bold = True
    p_b1.add_run(
        "Abarca la totalidad del año histórico 2025 (desde el 01/01/2025 hasta el 31/12/2025 22:00:00), con un volumen de "
        "4,037,300 registros horarios a nivel estación. Representa el régimen operativo de entrenamiento bajo el cual se optimizó "
        "el estimador Champion de producción (LightGBM). Para la auditoría de drift se extrajo una muestra estratificada representativa "
        "de 7,500 observaciones."
    )

    p_b2 = doc.add_paragraph(style='List Bullet')
    p_b2.add_run("Conjunto Actual (Producción 2026): ").font.bold = True
    p_b2.add_run(
        "Abarca el periodo posterior en servicio desde el 01/01/2026 hasta el 30/09/2026, con 3,078,500 registros horarios. "
        "Representa datos reales no vistos durante el entrenamiento original. Para la auditoría de drift se utilizó una muestra "
        "estratificada de 7,500 observaciones y para la suite de A/B testing se emplearon 50,000 registros para garantizar alta potencia estadística."
    )

    # 4. SECCIÓN 2: REPORTE DE DATA DRIFT CON EVIDENTLY
    add_custom_heading(doc, "2. Monitoreo y Auditoría de Data Drift con Evidently AI", level=1)

    doc.add_paragraph(
        "Se integró Evidently AI (evidently==0.7.23) para contrastar las distribuciones empíricas de las 17 variables predictoras del modelo. "
        "Se empleó la distancia Wasserstein normalizada (Earth Mover's Distance) para variables numéricas continuas y la divergencia "
        "Jensen-Shannon para variables discretas o de conteo. Se configuró un umbral crítico de deriva de 0.10 y un umbral de alerta temprana de 0.05."
    )

    add_callout(
        doc,
        title="Dictamen Ejecutivo de Observabilidad (Evidently AI)",
        text="Auditoría completada exitosamente sobre 17 características predictoras. Tasa de Dataset Drift Crítico: 0.0% "
             "(0/17 variables excedieron el umbral crítico de 0.10). Calidad de datos: 100% (cero valores nulos, infinitos "
             "o tipos de datos divergentes). Las características físicas e infraestructura se mantienen estables, concentrándose "
             "el desplazamiento en variables rodantes acumuladas.",
        bg_hex="F0F9FF",
        border_hex="003366"
    )

    fig_summary = FIGURES_DIR / "evidently_drift_summary_card.png"
    add_figure_with_caption(doc, fig_summary, "Figura 1: Ficha Ejecutiva de Auditoría de Data Drift y Calidad de Datos (Evidently AI).", width=Inches(5.7))

    fig_ranking = FIGURES_DIR / "evidently_drift_wasserstein_ranking.png"
    add_figure_with_caption(doc, fig_ranking, "Figura 2: Ranking de Deriva Estadística por Distancia Wasserstein y Jensen-Shannon en las 17 Variables de P2.", width=Inches(5.7))

    # 5. SECCIÓN 3: INTERPRETACIÓN DEL DRIFT Y CONSECUENCIAS OPERATIVAS
    add_custom_heading(doc, "3. Interpretación Técnica de Variables Afectadas e Implicaciones de Negocio", level=1)

    doc.add_paragraph(
        "Aunque ninguna variable sobrepasó el umbral crítico de 0.10, el ranking de deriva revela un gradiente "
        "sistemático que demanda atención técnica:"
    )

    doc.add_paragraph(
        "• Balance Rodante de 12 y 3 Horas (balance_rolling_12h: 0.0711, balance_rolling_3h: 0.0646): Representan el mayor desplazamiento relativo. "
        "Estas variables capturan la acumulación neta de bicicletas (llegadas menos salidas) en ventanas móviles. A inicios de 2026, la reactivación "
        "laboral y académica en el Área Metropolitana de Guadalajara acentuó los viajes pendulares unidireccionales en horas pico. Las estaciones ubicadas "
        "en distritos corporativos experimentaron ingresos más acelerados, mientras que estaciones habitacionales sufrieron vaciados más pronunciados, "
        "ensanchando las colas de la distribución empírica."
    )

    doc.add_paragraph(
        "• Lags Semanales (llegadas_lag_168: 0.0527, salidas_lag_168: 0.0391): El desfase entre semanas calendario entre 2025 y 2026 genera "
        "ligeras discrepancias en los patrones semanales de 7 días (168 horas), particularmente en torno a festividades y periodos no laborables."
    )

    doc.add_paragraph(
        "• Invarianza de Infraestructura Física: Variables geográficas (latitude: 0.033, longitude: 0.015), capacidad instalada (capacity: 0.013) "
        "y componentes cíclicos horarios (sin_hour: 0.012, cos_hour: 0.011) permanecieron casi idénticas, lo que confirma que la topología física "
        "de la red no sufrió modificaciones estructurales."
    )

    doc.add_paragraph(
        "Consecuencias Operativas en el CCO: Un sesgo en las variables de balance rodante incrementa la propensión del estimador a descalibrar "
        "sus probabilidades a posteriori. En horas pico, el modelo podría subestimar la probabilidad de desabasto en zonas críticas o activar falsas "
        "alarmas de saturación. Esto motivó la hipótesis de que un modelo con regularización reforzada y menor dependencia de variables acumuladas "
        "(Challenger) podría ofrecer mayor robustez en producción."
    )

    fig_dist = FIGURES_DIR / "evidently_distributions_drift.png"
    add_figure_with_caption(doc, fig_dist, "Figura 3: Contraste de Densidades Empíricas (KDE) entre Baseline 2025 y Producción 2026 para Variables Clave.", width=Inches(5.7))

    # 6. SECCIÓN 4: MODELO ALTERNATIVO Y A/B TESTING
    add_custom_heading(doc, "4. Versión Alternativa (Challenger) y Resultados del A/B Testing", level=1)

    doc.add_paragraph(
        "Para responder al drift detectado, se formuló una versión alternativa (Versión 2 Challenger: lgbm_challenger_v2) "
        "optimizada con LightGBM. Se aplicó regularización L1 y L2 (reg_alpha=0.1, reg_lambda=0.5), submuestreo aleatorio de columnas "
        "(colsample_bytree=0.80) para forzar al modelo a no depender exclusivamente de los balances rodantes, bagging con reemplazo "
        "(subsample=0.85) y límites en profundidad (max_depth=7, num_leaves=40). El modelo se registró formalmente en el Model Registry "
        "de MLflow (mibici-equipo30-p2-riesgo) como Versión 2 con alias @challenger, manteniendo la Versión 1 original como @champion."
    )

    doc.add_paragraph(
        "Ambas versiones fueron sometidas a una prueba A/B en condiciones de producción sobre 50,000 registros horarios estratificados del año 2026:"
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
    add_figure_with_caption(doc, fig_ab_panel, "Figura 4: Resultados Integrales de A/B Testing: Métricas Comparativas y Matrices de Confusión Normalizadas en Producción 2026.", width=Inches(5.7))

    add_callout(
        doc,
        title="Contraste Estadístico y Análisis de Hipótesis",
        text="La prueba de McNemar sobre predicciones concordantes y discordantes confirmó que la diferencia en clasificación "
             "es estadísticamente significativa (chi-cuadrado = 151.73, p < 0.001). El remuestreo bootstrap al 95% de confianza "
             "(400 réplicas) para Delta Macro F1 estableció un intervalo estrictamente negativo [-0.0051, -0.0031], confirmando "
             "que la Versión 1 Champion conserva una superioridad sistemática en balance multiclase.",
        bg_hex="F8FAFC",
        border_hex="003366"
    )

    # 7. SECCIÓN 5: RECOMENDACIÓN DE CONTINUOUS TRAINING
    add_custom_heading(doc, "5. Decisión de Versión y Recomendación de Continuous Training (CT)", level=1)

    doc.add_paragraph(
        "Decisión del A/B Testing: Se determina de manera concluyente MANTENER la Versión 1 (lgbm_profundo) con el alias activo "
        "@champion en producción. La justificación de negocio y operativa es determinante: el Champion sostiene un Recall en Desabasto "
        "superior (88.08% frente a 87.56%) y un Macro F1 superior (0.3704 frente a 0.3663). En un sistema de micromovilidad pública como MiBici, "
        "el desabasto es la falla más lesiva para el usuario (llegar y no encontrar bicicleta), mientras que la saturación permite al menos "
        "desviarse a una estación vecina. Sacrificar 0.52 puntos porcentuales de recall en desabasto para ganar 0.73 ms de latencia "
        "(3.50 ms vs. 4.23 ms, ambas muy por debajo del SLA de 100 ms) representa una degradación inaceptable del servicio."
    )

    doc.add_paragraph(
        "Estrategia de Continuous Training (CT) Propuesta: Para garantizar la vigencia del modelo conforme se acumulen nuevos datos en 2026, "
        "se define la siguiente arquitectura de automatización MLOps:"
    )

    p_ct1 = doc.add_paragraph(style='List Bullet')
    p_ct1.add_run("Disparadores Basados en Drift (Evidently AI): ").font.bold = True
    p_ct1.add_run("Ejecución semanal automática de DataDriftPreset. Si balance_rolling_12h excede una distancia Wasserstein de 0.10 o más del 25% de las características superan 0.08, se gatilla automáticamente el reentrenamiento.")

    p_ct2 = doc.add_paragraph(style='List Bullet')
    p_ct2.add_run("Disparadores de Desempeño Operativo: ").font.bold = True
    p_ct2.add_run("Si el Recall acumulado a 14 días para la clase desabasto cae por debajo del 85.0% o el Macro F1 disminuye de 0.35, se activa un pipeline de reentrenamiento correctivo de alta prioridad.")

    p_ct3 = doc.add_paragraph(style='List Bullet')
    p_ct3.add_run("Ventana Temporal y Regularización Híbrida: ").font.bold = True
    p_ct3.add_run("Ventana rodante de 12 meses con ponderación exponencial decreciente para dar mayor peso a los meses recientes, adoptando la regularización L1/L2 y colsample=0.80 explorados en el Challenger v2.")

    p_ct4 = doc.add_paragraph(style='List Bullet')
    p_ct4.add_run("Compuertas de Despliegue y Gobernanza: ").font.bold = True
    p_ct4.add_run("Ningún modelo candidato sustituirá al Champion activo sin satisfacer: (1) validación de esquema con cero errores, (2) latencia de inferencia menor a 10 ms por lote, y (3) paridad o superioridad estadística en Recall de Desabasto en un A/B test canario del 10% del tráfico durante 72 horas.")

    add_callout(
        doc,
        title="Protocolo de Gobernanza MLOps para Reentrenamiento Continuo",
        text="El modelo reentrenado se registrará en MLflow Model Registry como nueva versión con alias @candidate. "
             "Solo tras superar las 3 compuertas automáticas se ejecutará la transición atómica del alias @champion, "
             "notificando al equipo de MLOps y registrando los artefactos de auditoría.",
        bg_hex="F0FDF4",
        border_hex="16A34A"
    )

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
