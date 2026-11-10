"""Verifica HTTP y, opcionalmente, el contenedor que publica la API.

El JSON conserva las respuestas observadas. No genera capturas ni simula una
terminal. Devuelve 1 si falla cualquier comprobación y 2 para argumentos inválidos.
"""

import argparse
import json
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

import requests


def get_sample_payload():
    return {
        "capacity": 20,
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


def inspect_container(engine, name, host_port):
    """Conserva evidencia del motor sin registrar variables de entorno sensibles."""
    command = [engine, "inspect", name]
    result = {"command": command, "passed": False}
    try:
        completed = subprocess.run(
            command, capture_output=True, text=True, timeout=30, check=True
        )
        item = json.loads(completed.stdout)[0]
        state = item.get("State", {})
        result.update(
            {
                "id": item.get("Id"),
                "name": item.get("Name"),
                "image_id": item.get("Image"),
                "image_name": item.get("ImageName")
                or item.get("Config", {}).get("Image"),
                "running": state.get("Running", False),
                "status": state.get("Status"),
                "started_at": state.get("StartedAt"),
                "ports": item.get("NetworkSettings", {}).get("Ports", {}),
            }
        )
        result["expected_host_port"] = host_port
        result["published_port_matches"] = any(
            binding.get("HostPort") == str(host_port)
            for binding in (result["ports"].get("8000/tcp") or [])
        )
        result["passed"] = bool(
            result["id"] and result["running"] and result["published_port_matches"]
        )
    except (
        OSError,
        subprocess.SubprocessError,
        ValueError,
        IndexError,
        TypeError,
    ) as exc:
        result["error"] = str(exc)
    return result


def run_checks(base_url, timeout=5, container_engine=None, container_name=None):
    base_url = base_url.rstrip("/")
    payload = get_sample_payload()
    missing = {k: v for k, v in payload.items() if k != "salidas_lag_168"}
    cases = [
        ("Raíz", "GET", "/", None, 200),
        ("Salud", "GET", "/health", None, 200),
        ("Configuración del modelo", "GET", "/model-info", None, 200),
        ("Predicción", "POST", "/predict", payload, 200),
        ("Capacidad cero", "POST", "/predict", {**payload, "capacity": 0}, 422),
        (
            "Capacidad fraccionaria",
            "POST",
            "/predict",
            {**payload, "capacity": 0.5},
            422,
        ),
        (
            "Capacidad fuera de int32",
            "POST",
            "/predict",
            {**payload, "capacity": 2**31},
            422,
        ),
        (
            "Valor fuera de float32",
            "POST",
            "/predict",
            {**payload, "salidas_lag_1": 1e39},
            422,
        ),
        ("Campo extra", "POST", "/predict", {**payload, "campo_desconocido": 1}, 422),
        ("Campo faltante", "POST", "/predict", missing, 422),
    ]
    results = {
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "base_url": base_url,
        "evidence_scope": "container_and_http" if container_engine else "http_only",
        "tests": [],
    }
    with requests.Session() as session:
        for name, method, endpoint, body, expected in cases:
            item = {
                "name": name,
                "endpoint": endpoint,
                "method": method,
                "expected_code": expected,
                "passed": False,
            }
            if body is not None:
                item["request_payload"] = body
            started = time.perf_counter()
            try:
                response = session.request(
                    method, base_url + endpoint, json=body, timeout=timeout
                )
                item["status_code"] = response.status_code
                data = response.json()
                item["response"] = data
                valid = isinstance(data, dict)
                if expected == 422:
                    valid = valid and isinstance(data.get("detail"), list)
                elif endpoint == "/predict":
                    prediction = data.get("prediction") if valid else None
                    valid = type(prediction) is int and prediction in (0, 1, 2)
                elif endpoint == "/":
                    valid = valid and data.get("status") == "ok"
                elif endpoint == "/health":
                    valid = valid and data.get("status") == "healthy"
                else:
                    valid = valid and isinstance(data.get("model_uri"), str)
                item["passed"] = response.status_code == expected and valid
            except (requests.RequestException, ValueError) as exc:
                item["error"] = str(exc)
            item["latency_ms"] = round((time.perf_counter() - started) * 1000, 3)
            results["tests"].append(item)
    if container_engine:
        url = urlsplit(base_url)
        results["container"] = inspect_container(
            container_engine,
            container_name,
            url.port or (443 if url.scheme == "https" else 80),
        )
    passed = sum(item["passed"] for item in results["tests"])
    results["summary"] = {"passed": passed, "total": len(cases)}
    all_passed = passed == len(cases) and results.get("container", {}).get(
        "passed", True
    )
    results["overall_status"] = "PASS" if all_passed else "FAIL"
    return results


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--timeout", type=float, default=5)
    parser.add_argument("--output-json", default="reports/container_verification.json")
    parser.add_argument(
        "--container-engine", help="docker, podman o ruta al ejecutable"
    )
    parser.add_argument("--container-name")
    args = parser.parse_args(argv)
    if args.timeout <= 0 or not args.timeout < float("inf"):
        parser.error("--timeout debe ser positivo y finito")
    if bool(args.container_engine) != bool(args.container_name):
        parser.error("--container-engine y --container-name deben especificarse juntos")
    results = run_checks(
        args.base_url, args.timeout, args.container_engine, args.container_name
    )
    path = Path(args.output_json)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    summary = results["summary"]
    print(
        f"{results['overall_status']}: {summary['passed']}/{summary['total']} comprobaciones HTTP; alcance: {results['evidence_scope']}"
    )
    print(f"Resultados: {path}")
    return 0 if results["overall_status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
