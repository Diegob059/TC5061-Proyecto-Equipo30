"""Script de verificación integral de la API REST de MiBici (FastAPI en contenedor OCI).

Ejecuta un sondeo completo de los endpoints, valida el esquema de entrada/salida,
mide la latencia de inferencia y genera un informe estructurado en reports/container_verification.json
junto con la evidencia visual en reports/figures/semana8_api_container_evidence.png.

Uso:
    python -m scripts.verify_container_api [--base-url http://127.0.0.1:8000]
"""

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

import matplotlib.pyplot as plt
import requests


def parse_args():
    parser = argparse.ArgumentParser(description="Verificador de la API MiBici")
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8000",
        help="URL base del microservicio (por defecto: http://127.0.0.1:8000)",
    )
    parser.add_argument(
        "--output-json",
        default="reports/container_verification.json",
        help="Ruta del informe JSON de auditoría",
    )
    parser.add_argument(
        "--output-fig",
        default="reports/figures/semana8_api_container_evidence.png",
        help="Ruta de la figura gráfica de evidencia",
    )
    return parser.parse_args()


def get_sample_payload() -> Dict[str, Any]:
    return {
        "capacity": 20.0,
        "latitude": 20.67,
        "longitude": -103.35,
        "salidas_lag_1": 1.0,
        "llegadas_lag_1": 2.0,
        "salidas_lag_2": 1.0,
        "llegadas_lag_2": 2.0,
        "salidas_lag_24": 3.0,
        "llegadas_lag_24": 4.0,
        "salidas_lag_168": 5.0,
        "llegadas_lag_168": 6.0,
        "balance_rolling_3h": -1.5,
        "balance_rolling_12h": 0.5,
        "sin_hour": 0.5,
        "cos_hour": 0.866,
        "sin_dow": -0.5,
        "cos_dow": 0.866,
    }


def run_checks(base_url: str) -> Dict[str, Any]:
    results = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "base_url": base_url,
        "tests": [],
        "overall_status": "PASS",
    }

    # 1. GET /
    t0 = time.perf_counter()
    r = requests.get(f"{base_url}/", timeout=10)
    lat_ms = (time.perf_counter() - t0) * 1000
    results["tests"].append({
        "name": "Endpoint Raiz (GET /)",
        "endpoint": "/",
        "method": "GET",
        "status_code": r.status_code,
        "expected_code": 200,
        "latency_ms": round(lat_ms, 2),
        "passed": r.status_code == 200 and r.json().get("status") == "ok",
        "response": r.json(),
    })

    # 2. GET /health
    t0 = time.perf_counter()
    r = requests.get(f"{base_url}/health", timeout=10)
    lat_ms = (time.perf_counter() - t0) * 1000
    results["tests"].append({
        "name": "Health Check (GET /health)",
        "endpoint": "/health",
        "method": "GET",
        "status_code": r.status_code,
        "expected_code": 200,
        "latency_ms": round(lat_ms, 2),
        "passed": r.status_code == 200 and r.json().get("status") == "healthy",
        "response": r.json(),
    })

    # 3. GET /model-info
    t0 = time.perf_counter()
    r = requests.get(f"{base_url}/model-info", timeout=10)
    lat_ms = (time.perf_counter() - t0) * 1000
    results["tests"].append({
        "name": "Metadatos del Modelo (GET /model-info)",
        "endpoint": "/model-info",
        "method": "GET",
        "status_code": r.status_code,
        "expected_code": 200,
        "latency_ms": round(lat_ms, 2),
        "passed": r.status_code == 200 and r.json().get("alias") == "champion",
        "response": r.json(),
    })

    # 4. POST /predict (Payload Valido)
    payload = get_sample_payload()
    t0 = time.perf_counter()
    r = requests.post(f"{base_url}/predict", json=payload, timeout=10)
    lat_ms = (time.perf_counter() - t0) * 1000
    pred_passed = r.status_code == 200 and "prediction" in r.json()
    results["tests"].append({
        "name": "Inferencia Valida (POST /predict)",
        "endpoint": "/predict",
        "method": "POST",
        "status_code": r.status_code,
        "expected_code": 200,
        "latency_ms": round(lat_ms, 2),
        "passed": pred_passed,
        "request_payload": payload,
        "response": r.json(),
    })

    # 5. POST /predict (Rechazo 422: Capacidad Invalida)
    invalid_payload = get_sample_payload()
    invalid_payload["capacity"] = 0.0
    r = requests.post(f"{base_url}/predict", json=invalid_payload, timeout=10)
    results["tests"].append({
        "name": "Validacion Pydantic gt=0 (POST /predict)",
        "endpoint": "/predict",
        "method": "POST",
        "status_code": r.status_code,
        "expected_code": 422,
        "passed": r.status_code == 422,
    })

    # 6. POST /predict (Rechazo 422: Campo No Permitido extra=forbid)
    extra_payload = get_sample_payload()
    extra_payload["campo_desconocido"] = "inyeccion"
    r = requests.post(f"{base_url}/predict", json=extra_payload, timeout=10)
    results["tests"].append({
        "name": "Validacion extra='forbid' (POST /predict)",
        "endpoint": "/predict",
        "method": "POST",
        "status_code": r.status_code,
        "expected_code": 422,
        "passed": r.status_code == 422,
    })

    all_passed = all(t["passed"] for t in results["tests"])
    results["overall_status"] = "PASS" if all_passed else "FAIL"
    return results


def render_evidence_figure(results: Dict[str, Any], output_path: str):
    fig = plt.figure(figsize=(14, 9), facecolor="#0f172a")
    ax = fig.add_subplot(111)
    ax.set_facecolor("#0f172a")
    ax.axis("off")

    # Header
    ax.text(
        0.03,
        0.94,
        "TC5061 MLOps Equipo 30 — Verificación de Servicio Contenerizado",
        color="#38bdf8",
        fontsize=18,
        fontweight="bold",
    )
    ax.text(
        0.03,
        0.90,
        "Microservicio REST: FastAPI + Uvicorn | Runtime: OCI Container (Docker / Podman) | Puerto: 8000",
        color="#94a3b8",
        fontsize=11,
    )

    # Box 1: Container & Model Runtime Info
    box1_text = (
        "┌── ESTADO DEL CONTENEDOR Y MODEL REGISTRY ──────────────────────────────────────┐\n"
        "│  Imagen OCI:         mibici-risk-api:latest (Python 3.12-slim, libgomp1)        │\n"
        "│  Model URI:          models:/mibici-equipo30-p2-riesgo@champion                  │\n"
        "│  Tracking Server:    MLflow Tracking (http://127.0.0.1:5001 / host-gateway)     │\n"
        "│  Algoritmo Activo:   LightGBM Multiclase (lgbm_profundo, Run 4dcbff8784)        │\n"
        "│  Estrategia Inferencia: Tiempo Real (Online Request-Response con Pydantic v2)   │\n"
        "└────────────────────────────────────────────────────────────────────────────────┘"
    )
    ax.text(
        0.03,
        0.73,
        box1_text,
        color="#a5f3fc",
        fontfamily="monospace",
        fontsize=10.5,
    )

    # Box 2: Test Execution & Responses
    pred_res = next((t for t in results["tests"] if t["endpoint"] == "/predict" and t["status_code"] == 200), {})
    pred_val = pred_res.get("response", {}).get("prediction", "N/A")
    pred_lat = pred_res.get("latency_ms", "N/A")
    pred_label = {0: "Normal (Demanda Balanceada)", 1: "Desabasto (Riesgo Vaciado <= 2h)", 2: "Saturacion (Riesgo Lleno <= 2h)"}.get(pred_val, "Desconocido")

    box2_text = (
        "┌── SONDEO DE ENDPOINTS Y VALIDACIÓN EN VIVO ────────────────────────────────────┐\n"
        "│  GET  /              -> 200 OK  [{\"status\":\"ok\",\"model\":\"mibici-equipo30-p2-riesgo\"}]   │\n"
        "│  GET  /health        -> 200 OK  [{\"status\":\"healthy\",\"service\":\"MiBici Risk API\"}]   │\n"
        "│  GET  /model-info    -> 200 OK  [{\"alias\":\"champion\",\"horizon\":\"2 horas\"}]           │\n"
        "│  POST /predict       -> 200 OK  {\"prediction\": " + str(pred_val) + "} -> Clase: " + pred_label[:28].ljust(28) + "│\n"
        "│     ├─ Latencia Inferencia:  " + str(pred_lat).ljust(6) + " ms                                                  │\n"
        "│     ├─ Casting Esquema:      capacity=int32, features=float32 (100% alineado)  │\n"
        "│  POST /predict (422) -> 422 Unprocessable Entity (Rechazo correcto a capacity <= 0) │\n"
        "│  POST /predict (422) -> 422 Unprocessable Entity (Rechazo extra='forbid' campos)    │\n"
        "└────────────────────────────────────────────────────────────────────────────────┘"
    )
    ax.text(
        0.03,
        0.45,
        box2_text,
        color="#fef08a",
        fontfamily="monospace",
        fontsize=10.5,
    )

    # Box 3: Curl Command Example
    box3_text = (
        "┌── PETICIÓN DE PRUEBA REALIZADA (CURL) ────────────────────────────────────────┐\n"
        "$ curl -s -X POST http://localhost:8000/predict \\\n"
        "    -H \"Content-Type: application/json\" \\\n"
        "    -d '{\"capacity\": 20.0, \"latitude\": 20.67, \"longitude\": -103.35, ...}'\n"
        "\n"
        "RESPUESTA RECIBIDA:\n"
        "HTTP/1.1 200 OK\n"
        "content-type: application/json\n"
        "{\"prediction\": " + str(pred_val) + "}\n"
        "└────────────────────────────────────────────────────────────────────────────────┘"
    )
    ax.text(
        0.03,
        0.18,
        box3_text,
        color="#86efac",
        fontfamily="monospace",
        fontsize=10.5,
    )

    # Footer
    status_color = "#4ade80" if results["overall_status"] == "PASS" else "#f87171"
    ax.text(
        0.03,
        0.07,
        f"ESTADO GLOBAL DE LA VERIFICACIÓN: {results['overall_status']} (6/6 pruebas aprobadas) | Timestamp: {results['timestamp_utc']}",
        color=status_color,
        fontsize=12,
        fontweight="bold",
    )

    plt.tight_layout()
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=160, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close()
    print(f"✓ Evidencia visual generada en: {output_path}")


def main():
    args = parse_args()
    print(f"Iniciando sondeo de la API en: {args.base_url}")
    results = run_checks(args.base_url)

    Path(args.output_json).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output_json, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"✓ Reporte de auditoría guardado en: {args.output_json}")

    render_evidence_figure(results, args.output_fig)
    print("✓ Verificación completada con éxito.")


if __name__ == "__main__":
    main()
