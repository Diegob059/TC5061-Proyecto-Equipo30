"""Genera el reporte institucional desde la portada del Equipo 30 y evidencia JSON.

python scripts/generate_week10_report.py --skip-pdf
Para PDF se requiere LibreOffice accesible mediante --soffice o SOFFICE_BIN.
La conversión se realiza sobre una copia temporal; nunca altera la plantilla.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

from docx import Document
from docx.enum.table import WD_ALIGN_VERTICAL
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
EVIDENCE = ROOT / "reports/semana10"
TEMPLATE = DOCS / "assets/plantilla_institucional_equipo30.docx"
STEM = "TC5061_Operacion_FinOps_Equipo30"
CI_URL = "https://github.com/Diegob059/TC5061-Proyecto-Equipo30/actions/runs/45089840741"
BASE_COMMIT = "8b4e49ffa2b8727b4528b89a3a74e83fd5e98133"


def report_pages(load, costs, compose):
    junit = ET.parse(EVIDENCE / "revision_pytest.xml").getroot()
    suites = list(junit) if junit.tag == "testsuites" else [junit]
    if any(int(x.get("failures", 0)) or int(x.get("errors", 0)) for x in suites):
        raise ValueError("La evidencia de pruebas contiene errores")
    passed_tests = sum(int(x.get("tests", 0)) - int(x.get("skipped", 0)) for x in suites)
    rows = costs["workloads"]["realtime_1min"]["profiles"]
    by_key = {r["key"]: r for r in rows}
    standard = costs["workloads"]["standard_5min"]["profiles"]
    api_base = by_key["fargate_x86_baseline"]["compute_monthly_usd"]
    base_total = by_key["fargate_x86_baseline"]["total_monthly_usd"]
    scheduled = by_key["fargate_arm_scheduled"]
    savings_total = 100 * (1 - scheduled["total_monthly_usd"] / base_total)
    total_requests = sum(s["total_requests"] for s in load["scenarios"])
    prediction_requests = sum(s["predict_requests"] for s in load["scenarios"])
    throughput = costs["observed_telemetry"]["sustained_rps_peak"]
    budget = costs["assumptions"]["mlflow_monthly_usd"]
    passed, total = compose["summary"]["passed"], compose["summary"]["total"]
    load_rows = []
    for s in load["scenarios"]:
        load_rows.append([str(s['users']), s['duration'], f"{s['total_requests']:,}",
                          f"{s['rps_predict']:.2f}", f"{s['latency_p50_ms']:.0f} / {s['latency_p95_ms']:.0f}",
                          f"{s['api_resources']['cpu_max_perc']:.1f}", f"{s['api_resources']['mem_max_mib']:.1f}"])
    labels = ["Fargate x86 1 CPU 2 GiB 24 h", "Fargate ARM 0.5 CPU 1 GiB 24 h",
              "Fargate ARM 0.5 CPU 1 GiB 19 h", "Cloud Run 1 CPU 0.5 GiB serial"]
    cost_rows = [[label, f"${r['compute_monthly_usd']:.2f}", f"${r['total_monthly_usd']:.2f}",
                  f"${r['cost_per_1m_usd']:.2f}"] for label, r in zip(labels, rows)]
    return [
        [
            ("heading", "1 Orquestación y automatización"),
            ("paragraph", "La plataforma MiBici integra la API de riesgo de P2 con MLflow mediante Docker Compose. Las evidencias del 22 de noviembre de 2026 muestran operación sin errores HTTP en los ensayos de carga. El costo unitario se estima con supuestos explícitos; su validación en cada topología de nube sigue pendiente."),
            ("paragraph", "docker-compose.yml define api y mlflow en la red mibici_net, con el volumen mlflow_data para SQLite y artefactos. Ambos servicios tienen healthcheck y límites configurables de CPU y memoria. La API espera a que MLflow esté saludable, carga el modelo al iniciar y publica sus endpoints en localhost."),
            ("paragraph", "Un volumen nuevo requiere preparar y registrar el modelo real de P2. Primero se inicia MLflow, se configura MLFLOW_TRACKING_URI y se ejecutan p2_train y p2_register con el run seleccionado. El modelo sintético seed_ci_model.py se reserva para comprobar infraestructura y se identifica como tal."),
            ("code", "docker compose up -d --build mlflow\n# Registrar el modelo real según README antes de continuar\ndocker compose up -d --build\ndocker compose ps"),
            ("paragraph", f"La verificación de Compose conserva {passed}/{total} comprobaciones aprobadas de contrato HTTP y contenedor. El arranque habitual utiliza un solo comando una vez que el volumen contiene el modelo. Cambiar el alias requiere reiniciar la API para cargar la nueva versión."),
            ("heading2", "Integración y publicación continuas"),
            ("paragraph", "GitHub Actions ejecuta las suites de API y operación y las de pipelines y validación en Python 3.12. Después construye la imagen con caché de capas, valida Compose, registra un modelo sintético para la prueba de integración y comprueba los endpoints con Locust. En push a main publica la imagen en GHCR."),
            ("paragraph", "La corrida histórica #9 terminó en verde en main sobre el commit 8b4e49f e incluyó publicación en GHCR. Publicar una imagen acredita entrega al registro; el repositorio no automatiza su despliegue en un entorno de nube. La revisión actual incorpora regresiones de errores, costos e identidad del modelo; su resultado local se conserva por separado."),
            ("small", f"Evidencia CI histórica: {CI_URL}"),
            ("small", "Fuentes: docker-compose.yml; .github/workflows/ci-cd.yml; reports/semana10/compose_verification.json. La prueba de CI utiliza un modelo sintético y no acredita el desempeño del modelo de producción."),
        ],
        [
            ("heading", "2 Resultados de carga y recursos"),
            ("paragraph", f"Locust combinó POST /predict, GET /health y GET /model-info con ponderación 10:1:1 y pausas de 0.1 a 0.5 s. Los tres ensayos suman {total_requests:,} peticiones, de las cuales {prediction_requests:,} son predicciones; se registraron cero fallos. Los payloads son escenarios sintéticos de operación."),
            ("table", (["Usuarios", "Duración", "Peticiones", "Pred/s", "p50 / p95 ms", "CPU pico %", "RAM MiB"], load_rows, [0.63, 0.65, 0.90, 0.75, 1.10, 0.92, 0.85])),
            ("figure", ("semana10_locust_performance.png", "Figura 1. Throughput total y de predicción y percentiles de POST /predict.", 2.05)),
            ("paragraph", f"Con 100 usuarios se observaron 307.51 peticiones/s totales y {throughput:.2f} predicciones/s, p95 de 42 ms y p99 de 73 ms. Se reporta el throughput del ensayo; la duración y las pausas del generador no permiten establecer la capacidad máxima ni atribuir un cuello de botella a CPU."),
            ("figure", ("semana10_docker_stats.png", "Figura 2. CPU y memoria medidas durante los tres ensayos de carga.", 1.70)),
            ("small", "La API alcanzó 173.1 MiB y 79.6% de CPU; MLflow, 734.5 MiB. Se guardaron 10, 15 y 15 muestras por contenedor, aproximadamente cada 3 s. La estabilidad observada en ensayos de 30-45 s no acredita ausencia de fugas a largo plazo. Fuentes: load_test_summary.json, docker_stats.csv y locust_*_stats.csv."),
        ],
        [
            ("heading", "3 Costo por inferencia"),
            ("paragraph", "Se modelan 470 estaciones, 19 h/día y 30.4 días/mes. Consultar cada 5 minutos produce 3,257,664 inferencias/mes; cada minuto, 16,288,320. Estas frecuencias y la ventana de operación son supuestos de demanda. La estimación asume una réplica por topología, pendiente de validar con carga en cada configuración."),
            ("paragraph", "Para servicios permanentes, costo API = tarifa horaria × horas activas. Costo de cómputo del sistema = costo API + presupuesto MLflow. Costo por inferencia = costo del sistema / inferencias mensuales. AWS Fargate x86 usa 0.04048 USD/vCPU-h y 0.004445 USD/GiB-h; ARM usa 0.03238 y 0.00356, respectivamente [1]."),
            ("paragraph", f"El presupuesto de MLflow es ${budget:.2f}/mes, correspondiente al supuesto de otra tarea Fargate x86 de 1 vCPU y 2 GiB durante 730 h. Se suma a todos los escenarios. La tabla usa 16.29 millones de inferencias/mes y distingue el costo de la API del cómputo conjunto."),
            ("table", (["Topología de la API", "API USD/mes", "Con MLflow USD/mes", "USD/1M con MLflow"], cost_rows, [2.62, 1.17, 1.38, 1.23])),
            ("figure", ("semana10_finops_costs.png", "Figura 3. Proyección de cómputo con el mismo presupuesto MLflow en cada topología.", 2.30)),
            ("paragraph", f"La API ARM programada pasa de ${api_base:.2f} a ${scheduled['compute_monthly_usd']:.2f}/mes: ahorro estimado de 68.3% en la API y {savings_total:.1f}% en el cómputo conjunto. No se ha medido el desempeño con 0.5 vCPU ARM. Al extrapolar {throughput:.2f} pred/s a 730 h se obtienen 673,924,320 inferencias; esta cifra no demuestra capacidad mensual sostenible."),
            ("small", "Alcance: cómputo de API y presupuesto MLflow. Se excluyen almacenamiento persistente, transferencia, IPv4, balanceador, logs, entrenamiento e impuestos; el costo total de propiedad será mayor. Tarifas de referencia consultadas el 22 de noviembre de 2026. EC2 Savings Plans se omite por falta de cotización verificable."),
        ],
        [
            ("heading", "4 Interpretación y mejoras verificables"),
            ("paragraph", f"Cloud Run se calcula como un escenario sin solicitudes solapadas y con redondeo a 100 ms por periodo aislado, sin nivel gratuito ni arranques en frío. Para 1 vCPU y 0.5 GiB: costo por petición = 0.1 × (0.000024 + 0.5 × 0.0000025) + 0.40/1,000,000 [2]. El escenario cuesta ${by_key['cloudrun_serverless']['compute_monthly_usd']:.2f}/mes para la API a 16.29M y ${standard[-1]['compute_monthly_usd']:.2f} a 3.26M. La concurrencia real puede cambiar el costo; el ahorro previo de 93% no queda sustentado por esta corrección."),
            ("paragraph", "La memoria observada motiva evaluar una asignación menor. Reducir CPU, migrar a ARM, apagar fuera de la ventana prevista o procesar estaciones en lotes son propuestas que requieren benchmark. No se atribuye un ahorro de CPU mayor a 70% al procesamiento por lotes porque ese endpoint no fue implementado ni medido."),
            ("heading2", "Calidad de la ejecución y trazabilidad"),
            ("paragraph", "El ejecutor corregido conserva los fallos de Locust y de docker stats, devuelve error cuando la corrida falla y representa mediciones ausentes con null. Lee salidas nuevas de cada ejecución para impedir que un CSV anterior aparente una prueba exitosa. La API resuelve champion a una versión fija al arrancar y expone versión, run_id, origen y fecha de carga."),
            ("paragraph", "La evidencia histórica registra champion sin versión exacta ni run_id. Se conserva como medición histórica con procedencia incompleta; no se le asigna retrospectivamente una identidad. Las nuevas corridas guardan la identidad al inicio y al final y rechazan modelos sintéticos, salvo habilitación explícita para evaluar infraestructura."),
            ("small", f"Validación de esta revisión: {passed_tests} pruebas locales aprobadas de API, verificador, operación y regresiones; JUnit en reports/semana10/revision_pytest.xml. No se repitió el ensayo de carga ni se certifica la publicación de esta rama mediante el CI histórico."),
            ("heading2", "Trabajo del equipo y referencias"),
            ("paragraph", "La implementación original de operación y sus ajustes se integraron en las PR #50, #51 y #52. Esta revisión añade las correcciones de QA y FinOps y el formato institucional del equipo. Las revisiones entre compañeros deben quedar documentadas en GitHub; no se atribuyen aprobaciones no registradas."),
            ("small", "[1] AWS. AWS Fargate Pricing. https://aws.amazon.com/fargate/pricing/\n[2] Google Cloud. Cloud Run pricing. https://cloud.google.com/run/pricing\nConsulta: 22 de noviembre de 2026. Código base y evidencia histórica: commit 8b4e49f del repositorio del Equipo 30. Fuentes locales: reports/semana10/finops_summary.json y CSV de carga; scripts/finops_analysis.py y run_load_and_monitor.py; api/model_loader.py."),
        ],
    ]


def add_table(doc, headers, rows, widths):
    table = doc.add_table(rows=1, cols=len(headers))
    table.autofit = False
    for col, width in zip(table.columns, widths):
        col.width = Inches(width)
    for i, values in enumerate([headers] + rows):
        cells = table.rows[0].cells if i == 0 else table.add_row().cells
        for j, (cell, value) in enumerate(zip(cells, values)):
            cell.width = Inches(widths[j])
            cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            pr = cell._tc.get_or_add_tcPr()
            shade = OxmlElement('w:shd'); shade.set(qn('w:fill'), '203F58' if i == 0 else ('F1F5F8' if i % 2 == 0 else 'FFFFFF'));pr.append(shade)
            borders = OxmlElement('w:tcBorders')
            for edge in ('top','left','bottom','right'):
                el=OxmlElement('w:'+edge);el.set(qn('w:val'),'single');el.set(qn('w:sz'),'4');el.set(qn('w:color'),'D9D9D9');borders.append(el)
            pr.append(borders)
            margins = OxmlElement('w:tcMar')
            for edge in ('top','bottom','left','right'):
                el=OxmlElement('w:'+edge);el.set(qn('w:w'),'70');el.set(qn('w:type'),'dxa');margins.append(el)
            pr.append(margins)
            p=cell.paragraphs[0];p.paragraph_format.space_after=Pt(0);p.paragraph_format.line_spacing=1.1
            p.alignment=WD_ALIGN_PARAGRAPH.LEFT if j==0 else WD_ALIGN_PARAGRAPH.CENTER
            r=p.add_run(value);r.font.name='Calibri';r.font.size=Pt(9);r.bold=i==0;r.font.color.rgb=RGBColor.from_string('FFFFFF' if i==0 else '000000')
        trpr=table.rows[i]._tr.get_or_add_trPr();trpr.append(OxmlElement('w:cantSplit'))
        if i==0:trpr.append(OxmlElement('w:tblHeader'))
    doc.add_paragraph().paragraph_format.space_after=Pt(2)


def build_docx(pages):
    doc=Document(TEMPLATE)
    for index, text in {4:'Operación y análisis FinOps\npara la plataforma MiBici',6:'Proyecto integrador\nEntregable 7 Actividad 9',16:'22 de noviembre de 2026'}.items():
        p=doc.paragraphs[index]
        p.runs[0].text=text
        for r in p.runs[1:]:r.text=''
    normal=doc.styles['Normal'];normal.font.name='Calibri';normal.font.size=Pt(11);normal.paragraph_format.line_spacing=1.15;normal.paragraph_format.space_after=Pt(6)
    for name in ('Title','Heading 1','Heading 2'):
        doc.styles[name].font.color.rgb=RGBColor(0,0,0)
    doc.core_properties.title='Operación y análisis FinOps para la plataforma MiBici'
    doc.core_properties.author='Equipo 30'
    for page in pages:
        for index,(kind,value) in enumerate(page):
            if kind.startswith('heading'):
                p=doc.add_paragraph(value,'Heading 1' if kind=='heading' else 'Heading 2')
                p.paragraph_format.page_break_before=index==0
                p.paragraph_format.space_before=Pt(0 if index==0 else 8);p.paragraph_format.space_after=Pt(7)
            elif kind in ('paragraph','small','code'):
                style={'paragraph':'Normal','small':'Small','code':'Code'}[kind]
                p=doc.add_paragraph(value,style)
                p.paragraph_format.line_spacing=1.15
                if kind=='small':p.paragraph_format.space_after=Pt(6)
                if kind in ('small','code'):p.alignment=WD_ALIGN_PARAGRAPH.LEFT
            elif kind=='table':add_table(doc,*value)
            elif kind=='figure':
                filename,caption,height=value
                p=doc.add_paragraph();p.alignment=WD_ALIGN_PARAGRAPH.CENTER;p.paragraph_format.space_after=Pt(2);p.paragraph_format.keep_with_next=True
                p.add_run().add_picture(str(ROOT/'reports/figures'/filename),width=Inches(6.8),height=Inches(height))
                cap=doc.add_paragraph(caption,'Small');cap.paragraph_format.space_after=Pt(6)
    path=DOCS/f'{STEM}.docx';doc.save(path)
    return path


def build_markdown(pages):
    lines=['# Operación y análisis FinOps para la plataforma MiBici','','Equipo 30 · TC5061 · 22 de noviembre de 2026','']
    for page in pages:
        for kind,value in page:
            if kind.startswith('heading'):lines+=['## '+value,'']
            elif kind in ('paragraph','small'):lines += [value,'']
            elif kind=='code':lines+=['```bash',value,'```','']
            elif kind=='figure':lines += [f'![{value[1]}](../reports/figures/{value[0]})',value[1],'']
            elif kind=='table':
                headers,rows,_=value
                lines+=['| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |']
                lines+=['| '+' | '.join(row)+' |' for row in rows];lines+=['']
    (DOCS/f'{STEM}.md').write_text('\n'.join(lines).rstrip()+'\n')


def compile_pdf(path, executable):
    if not executable:
        raise RuntimeError('Para exportar PDF indique --soffice o use --skip-pdf y convierta el DOCX en su editor')
    with tempfile.TemporaryDirectory() as temp:
        profile=Path(temp)/'profile'
        subprocess.run([executable,f'-env:UserInstallation={profile.as_uri()}','--headless','--convert-to','pdf','--outdir',temp,str(path)],check=True,capture_output=True,text=True)
        pdf=Path(temp)/f'{STEM}.pdf'
        if not pdf.exists() or len(PdfReader(pdf).pages)!=5:
            raise RuntimeError('La exportación debe conservar cinco páginas; revisar la maquetación')
        shutil.copy2(pdf,DOCS/pdf.name)
        output=ROOT/'output/pdf';output.mkdir(parents=True,exist_ok=True);shutil.copy2(pdf,output/pdf.name)
    return DOCS/f'{STEM}.pdf'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--skip-pdf',action='store_true')
    parser.add_argument('--soffice',default=os.getenv('SOFFICE_BIN') or shutil.which('soffice'))
    args=parser.parse_args()
    load=json.loads((EVIDENCE/'load_test_summary.json').read_text())
    costs=json.loads((EVIDENCE/'finops_summary.json').read_text())
    compose=json.loads((EVIDENCE/'compose_verification.json').read_text())
    if compose.get('overall_status')!='PASS':raise ValueError('La evidencia Compose no está aprobada')
    pages=report_pages(load,costs,compose)
    path=build_docx(pages);build_markdown(pages)
    print(path)
    if not args.skip_pdf:print(compile_pdf(path,args.soffice))


if __name__=='__main__':main()
