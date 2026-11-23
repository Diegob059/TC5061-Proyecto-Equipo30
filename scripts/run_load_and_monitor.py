"""Ejecuta Locust y conserva fallos, identidad del modelo y telemetría de Docker.

El código de salida es 0 al aprobar, 1 por carga/telemetría fallida y 2 por
argumentos o prerrequisitos inválidos. Una medición ausente se representa con
null, nunca con consumo cero. Las salidas de cada escenario se generan primero
en un directorio temporal para impedir la lectura de CSV de una corrida anterior.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

SCENARIOS = [
    {"name": "low_10u", "label": "Carga Baja (10 usuarios)", "users": 10, "spawn_rate": 5, "duration": "30s"},
    {"name": "medium_50u", "label": "Carga Media (50 usuarios)", "users": 50, "spawn_rate": 10, "duration": "45s"},
    {"name": "high_100u", "label": "Carga Alta (100 usuarios)", "users": 100, "spawn_rate": 20, "duration": "45s"},
]


def parse_mem_mib(mem_str: str) -> float:
    used = mem_str.split("/")[0].strip()
    match = re.fullmatch(r"([0-9.]+)\s*([A-Za-z]+)", used)
    factors = {"b": 1 / 1024**2, "kib": 1 / 1024, "kb": 1 / 1024,
               "mib": 1, "mb": 1, "gib": 1024, "gb": 1024}
    if not match or match[2].lower() not in factors:
        raise ValueError(f"Memoria no interpretable: {mem_str!r}")
    value = float(match[1]) * factors[match[2].lower()]
    if not math.isfinite(value) or value < 0:
        raise ValueError("Memoria inválida")
    return value


def parse_percent(pct_str: str) -> float:
    value = float(pct_str.replace("%", "").strip())
    if not math.isfinite(value) or value < 0:
        raise ValueError(f"Porcentaje inválido: {pct_str!r}")
    return value


def aggregate_resources(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return dict(sample_count=0, cpu_avg_perc=None, cpu_max_perc=None,
                    mem_avg_mib=None, mem_max_mib=None)
    return dict(
        sample_count=len(rows),
        cpu_avg_perc=round(sum(r["cpu_perc"] for r in rows) / len(rows), 2),
        cpu_max_perc=round(max(r["cpu_perc"] for r in rows), 2),
        mem_avg_mib=round(sum(r["mem_mib"] for r in rows) / len(rows), 2),
        mem_max_mib=round(max(r["mem_mib"] for r in rows), 2),
    )


def sample_docker_stats(stop_event, records, scenario_name, containers,
                        engine="docker", interval_s=1.0, errors=None):
    errors = errors if errors is not None else []
    started = time.monotonic()
    while not stop_event.is_set():
        try:
            proc = subprocess.run(
                [engine, "stats", "--no-stream", "--format", "{{json .}}", *containers],
                capture_output=True, text=True, timeout=8, check=False)
            if proc.returncode:
                raise RuntimeError(proc.stderr.strip() or f"docker stats: exit {proc.returncode}")
            items = [json.loads(line) for line in proc.stdout.splitlines() if line.strip()]
            if not items:
                raise ValueError("docker stats no devolvió muestras")
            for item in items:
                records.append(dict(
                    timestamp_utc=datetime.now(UTC).isoformat(), scenario=scenario_name,
                    elapsed_s=round(time.monotonic() - started, 2), container=item["Name"],
                    cpu_perc=parse_percent(item["CPUPerc"]),
                    mem_mib=round(parse_mem_mib(item["MemUsage"]), 2),
                    mem_perc=parse_percent(item["MemPerc"]), mem_raw=item["MemUsage"],
                ))
        except (OSError, subprocess.SubprocessError, ValueError, KeyError, RuntimeError) as exc:
            errors.append(f"{scenario_name}: monitoreo: {exc}")
        stop_event.wait(interval_s)


def discover_compose_containers(engine="docker") -> dict[str, str]:
    containers = {}
    for service in ("api", "mlflow"):
        proc = subprocess.run([engine, "compose", "ps", "-q", service],
                              capture_output=True, text=True, check=True)
        ids = proc.stdout.split()
        if len(ids) != 1:
            raise ValueError(f"Se requiere exactamente un contenedor Compose activo para {service}")
        containers[service] = ids[0]
    return containers


def inspect_containers(containers, engine="docker") -> dict[str, Any]:
    result = {}
    for service, cid in containers.items():
        proc = subprocess.run([engine, "inspect", cid], capture_output=True, text=True, check=True)
        item = json.loads(proc.stdout)[0]
        result[service] = dict(container_id=item["Id"], name=item["Name"].lstrip("/"),
                               image_id=item["Image"], image=item["Config"]["Image"],
                               cpu_limit=item["HostConfig"].get("NanoCpus", 0) / 1e9,
                               memory_limit_bytes=item["HostConfig"].get("Memory"))
    return result


def fetch_model_metadata(host: str) -> dict[str, Any]:
    with urllib.request.urlopen(host.rstrip("/") + "/model-info", timeout=10) as response:
        metadata = json.load(response)
    if not metadata.get("model_version") or not metadata.get("run_id"):
        raise ValueError("La API debe identificar la versión cargada y su run_id antes de medir carga")
    return metadata


def summarize_locust(stats_csv: Path) -> dict[str, Any]:
    df = pd.read_csv(stats_csv)
    agg = df[df["Name"] == "Aggregated"].iloc[0]
    pred = df[df["Name"] == "POST /predict"].iloc[0]
    total, failures = int(agg["Request Count"]), int(agg["Failure Count"])
    if total <= 0 or int(pred["Request Count"]) <= 0:
        raise ValueError("La corrida debe contener peticiones y predicciones")
    return dict(total_requests=total, failure_count=failures,
                error_rate_pct=round(failures / total * 100, 4),
                rps_aggregated=round(float(agg["Requests/s"]), 2),
                rps_predict=round(float(pred["Requests/s"]), 2),
                predict_requests=int(pred["Request Count"]),
                predict_failures=int(pred["Failure Count"]),
                latency_avg_ms=round(float(pred["Average Response Time"]), 2),
                latency_p50_ms=float(pred["50%"]), latency_p95_ms=float(pred["95%"]),
                latency_p99_ms=float(pred["99%"]), latency_max_ms=float(pred["Max Response Time"]))


def run_suite(host: str, output_dir: Path, engine="docker", allow_synthetic=False) -> dict[str, Any]:
    containers = discover_compose_containers(engine)
    inspected = inspect_containers(containers, engine)
    model_before = fetch_model_metadata(host)
    if model_before.get("origin") == "ci_smoke_synthetic" and not allow_synthetic:
        raise ValueError("Modelo sintético de CI: use --allow-synthetic solo para validar infraestructura")
    output_dir.mkdir(parents=True, exist_ok=True)
    records, scenarios, errors = [], [], []
    for sc in SCENARIOS:
        sc_errors = []
        stop = threading.Event()
        thread = threading.Thread(target=sample_docker_stats,
                                  args=(stop, records, sc["name"], list(containers.values()), engine, 1.0, sc_errors),
                                  daemon=True)
        result = {**sc, "locust_exit_code": None}
        # Ningún CSV previo puede confundirse con el de esta ejecución.
        with tempfile.TemporaryDirectory(dir=output_dir) as temp:
            prefix = Path(temp) / f"locust_{sc['name']}"
            cmd = [sys.executable, "-m", "locust", "-f", "load_tests/locustfile.py",
                   "--host", host, "--headless", "-u", str(sc["users"]),
                   "-r", str(sc["spawn_rate"]), "-t", sc["duration"],
                   "--csv", str(prefix), "--csv-full-history", "--html", str(prefix) + ".html", "--only-summary"]
            thread.start()
            try:
                proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
                result["locust_exit_code"] = proc.returncode
                (Path(temp) / f"locust_{sc['name']}.log").write_text(proc.stdout + proc.stderr)
                if proc.returncode != 0:
                    sc_errors.append(f"Locust terminó con código {proc.returncode}")
                result.update(summarize_locust(Path(str(prefix) + "_stats.csv")))
                if result["failure_count"]:
                    sc_errors.append(f"{result['failure_count']} peticiones fallaron")
            except (OSError, ValueError, KeyError, IndexError, pd.errors.ParserError) as exc:
                sc_errors.append(f"No se pudo completar Locust: {exc}")
            finally:
                stop.set()
                thread.join()  # El subprocess del monitor tiene timeout de 8 segundos.
                for path in Path(temp).iterdir():
                    shutil.copy2(path, output_dir / path.name)
        for service in ("api", "mlflow"):
            rows = [r for r in records if r["scenario"] == sc["name"] and
                    r["container"].lstrip("/") == inspected[service]["name"]]
            result[f"{service}_resources"] = aggregate_resources(rows)
            if not rows:
                sc_errors.append(f"Falta telemetría de {service}")
        result.update(status="FAIL" if sc_errors else "PASS", errors=sc_errors)
        scenarios.append(result)
        errors.extend(f"{sc['name']}: {e}" for e in sc_errors)
    try:
        model_after = fetch_model_metadata(host)
        if any(model_before.get(key) != model_after.get(key)
               for key in ("model_version", "run_id", "loaded_at_utc")):
            errors.append("La identidad o el proceso del modelo cambió durante la carga")
    except (OSError, ValueError) as exc:
        model_after = None
        errors.append(f"No se pudo comprobar el modelo al finalizar: {exc}")
    if records:
        with (output_dir / "docker_stats.csv").open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(records[0]))
            writer.writeheader()
            writer.writerows(records)
    summary = dict(generated_at_utc=datetime.now(UTC).isoformat(), host=host,
                   container_engine=engine, containers=inspected,
                   generator_platform=dict(system=platform.system(), machine=platform.machine(), python=platform.python_version()),
                   model_before=model_before, model_after=model_after,
                   evidence_scope="synthetic_model" if model_before.get("origin") == "ci_smoke_synthetic" else "identified_model",
                   scenarios=scenarios, overall_status="FAIL" if errors else "PASS", errors=errors)
    (output_dir / "load_test_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    return summary


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="http://127.0.0.1:8000")
    parser.add_argument("--output-dir", default="reports/semana10")
    parser.add_argument("--engine", default="docker")
    parser.add_argument("--allow-synthetic", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = run_suite(args.host, Path(args.output_dir), args.engine, args.allow_synthetic)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f"No se inició la medición: {exc}", file=sys.stderr)
        return 2
    print(f"{result['overall_status']}: {Path(args.output_dir) / 'load_test_summary.json'}")
    return 0 if result["overall_status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
