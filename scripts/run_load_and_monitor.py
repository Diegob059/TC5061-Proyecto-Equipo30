"""Ejecuta pruebas de carga escalonadas con Locust mientras monitorea `docker stats`.

Corre tres escenarios secuenciales contra la API contenerizada (10, 50 y 100 usuarios
concurrentes) registrando simultáneamente el consumo de CPU y memoria de los
contenedores `api` y `mlflow` cada segundo.

Salida generada en `reports/semana10/`:
- `locust_{10u,50u,100u}_stats.csv`, `*_stats_history.csv`, `*_failures.csv`, `*.html`
- `docker_stats.csv`: telemetría por segundo de CPU (%) y Memoria (MiB) por contenedor y escenario
- `load_test_summary.json`: resumen consolidado para el análisis FinOps y el reporte PDF
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import sys
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

SCENARIOS = [
    {"name": "low_10u", "label": "Carga Baja (10 usuarios)", "users": 10, "spawn_rate": 5, "duration": "30s"},
    {"name": "medium_50u", "label": "Carga Media (50 usuarios)", "users": 50, "spawn_rate": 10, "duration": "45s"},
    {"name": "high_100u", "label": "Carga Alta / Estrés (100 usuarios)", "users": 100, "spawn_rate": 20, "duration": "45s"},
]


def parse_mem_mib(mem_str: str) -> float:
    """Convierte cadenas de `docker stats` como '184.5MiB / 1GiB' a MiB flotante."""
    used = mem_str.split("/")[0].strip()
    match = re.match(r"([0-9.]+)\s*([A-Za-z]+)", used)
    if not match:
        return 0.0
    val = float(match.group(1))
    unit = match.group(2).lower()
    if unit in ("b",):
        return val / (1024.0 * 1024.0)
    if unit in ("kib", "kb", "k"):
        return val / 1024.0
    if unit in ("mib", "mb", "m"):
        return val
    if unit in ("gib", "gb", "g"):
        return val * 1024.0
    return val


def parse_percent(pct_str: str) -> float:
    """Convierte '42.15%' a 42.15."""
    try:
        return float(pct_str.replace("%", "").strip())
    except ValueError:
        return 0.0


def sample_docker_stats(
    stop_event: threading.Event,
    records: list[dict[str, Any]],
    scenario_name: str,
    containers: list[str],
    engine: str = "docker",
    interval_s: float = 1.0,
) -> None:
    """Hilo de monitoreo continuo de CPU y RAM de los contenedores activos."""
    t_start = time.monotonic()
    while not stop_event.is_set():
        cmd = [engine, "stats", "--no-stream", "--format", "{{json .}}", *containers]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=8, check=False)
            ts = datetime.now(UTC).isoformat()
            elapsed = round(time.monotonic() - t_start, 2)
            for line in proc.stdout.strip().splitlines():
                if not line.strip():
                    continue
                item = json.loads(line)
                records.append(
                    {
                        "timestamp_utc": ts,
                        "scenario": scenario_name,
                        "elapsed_s": elapsed,
                        "container": item.get("Name", ""),
                        "cpu_perc": parse_percent(item.get("CPUPerc", "0%")),
                        "mem_mib": round(parse_mem_mib(item.get("MemUsage", "0MiB / 0MiB")), 2),
                        "mem_perc": parse_percent(item.get("MemPerc", "0%")),
                        "mem_raw": item.get("MemUsage", ""),
                        "net_io": item.get("NetIO", ""),
                        "pids": item.get("PIDs", ""),
                    }
                )
        except Exception:
            pass
        stop_event.wait(interval_s)


def discover_compose_containers(engine: str = "docker") -> list[str]:
    """Obtiene los nombres de los contenedores `api` y `mlflow` activos en Compose."""
    proc = subprocess.run(
        [engine, "compose", "ps", "--format", "{{.Name}}"],
        capture_output=True,
        text=True,
        check=False,
    )
    names = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
    if names:
        return names
    proc = subprocess.run(
        [engine, "ps", "--format", "{{.Names}}"],
        capture_output=True,
        text=True,
        check=False,
    )
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


def run_suite(host: str, output_dir: Path, engine: str = "docker") -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    containers = discover_compose_containers(engine=engine)
    print(f"Contenedores monitoreados ({engine}): {containers}")

    all_stats_records: list[dict[str, Any]] = []
    scenario_summaries: list[dict[str, Any]] = []

    for sc in SCENARIOS:
        name = sc["name"]
        csv_prefix = output_dir / f"locust_{name}"
        html_path = output_dir / f"locust_{name}.html"
        print(f"\n=== Ejecutando {sc['label']} ({sc['users']}u, spawn {sc['spawn_rate']}/s, {sc['duration']}) ===")

        stop_event = threading.Event()
        monitor_thread = threading.Thread(
            target=sample_docker_stats,
            args=(stop_event, all_stats_records, name, containers, engine, 1.0),
            daemon=True,
        )
        monitor_thread.start()

        locust_cmd = [
            sys.executable,
            "-m",
            "locust",
            "-f",
            "load_tests/locustfile.py",
            "--host",
            host,
            "--headless",
            "-u",
            str(sc["users"]),
            "-r",
            str(sc["spawn_rate"]),
            "-t",
            sc["duration"],
            "--csv",
            str(csv_prefix),
            "--csv-full-history",
            "--html",
            str(html_path),
            "--only-summary",
        ]
        try:
            proc = subprocess.run(locust_cmd, capture_output=True, text=True, check=False)
            print(proc.stdout[-1200:] if proc.stdout else "")
            if proc.returncode not in (0, 1):
                print(proc.stderr[-800:])
        finally:
            stop_event.set()
            monitor_thread.join(timeout=5)

        stats_csv = Path(f"{csv_prefix}_stats.csv")
        df_stats = pd.read_csv(stats_csv)
        agg = df_stats[df_stats["Name"] == "Aggregated"].iloc[0]
        pred_rows = df_stats[df_stats["Name"] == "POST /predict"]
        pred = pred_rows.iloc[0] if not pred_rows.empty else agg

        sc_docker = [r for r in all_stats_records if r["scenario"] == name]
        api_docker = [r for r in sc_docker if "api" in r["container"].lower()]
        mlflow_docker = [r for r in sc_docker if "mlflow" in r["container"].lower()]

        def agg_res(rows: list[dict[str, Any]]) -> dict[str, float]:
            if not rows:
                return {"cpu_avg_perc": 0.0, "cpu_max_perc": 0.0, "mem_avg_mib": 0.0, "mem_max_mib": 0.0}
            return {
                "cpu_avg_perc": round(sum(r["cpu_perc"] for r in rows) / len(rows), 2),
                "cpu_max_perc": round(max(r["cpu_perc"] for r in rows), 2),
                "mem_avg_mib": round(sum(r["mem_mib"] for r in rows) / len(rows), 2),
                "mem_max_mib": round(max(r["mem_mib"] for r in rows), 2),
            }

        total_reqs = int(agg["Request Count"])
        fail_reqs = int(agg["Failure Count"])
        scenario_summaries.append(
            {
                "name": name,
                "label": sc["label"],
                "users": sc["users"],
                "spawn_rate": sc["spawn_rate"],
                "duration": sc["duration"],
                "total_requests": total_reqs,
                "failure_count": fail_reqs,
                "error_rate_pct": round((fail_reqs / total_reqs * 100.0) if total_reqs else 0.0, 4),
                "rps_aggregated": round(float(agg["Requests/s"]), 2),
                "rps_predict": round(float(pred["Requests/s"]), 2),
                "predict_requests": int(pred["Request Count"]),
                "latency_avg_ms": round(float(pred["Average Response Time"]), 2),
                "latency_p50_ms": round(float(pred["50%"]), 2),
                "latency_p95_ms": round(float(pred["95%"]), 2),
                "latency_p99_ms": round(float(pred["99%"]), 2),
                "latency_max_ms": round(float(pred["Max Response Time"]), 2),
                "api_resources": agg_res(api_docker),
                "mlflow_resources": agg_res(mlflow_docker),
            }
        )
        time.sleep(3)

    docker_csv = output_dir / "docker_stats.csv"
    if all_stats_records:
        with docker_csv.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(all_stats_records[0].keys()))
            writer.writeheader()
            writer.writerows(all_stats_records)

    summary = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "host": host,
        "container_engine": engine,
        "containers": containers,
        "scenarios": scenario_summaries,
    }
    summary_path = output_dir / "load_test_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\n✓ Telemetría guardada en {docker_csv}")
    print(f"✓ Resumen consolidado guardado en {summary_path}")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="http://127.0.0.1:8000")
    parser.add_argument("--output-dir", default="reports/semana10")
    parser.add_argument("--engine", default="docker")
    args = parser.parse_args()
    run_suite(host=args.host, output_dir=Path(args.output_dir), engine=args.engine)


if __name__ == "__main__":
    main()
