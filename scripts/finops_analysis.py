"""Análisis FinOps y generación de gráficas de desempeño y costos (Semana 10).

Consume los resultados reales generados por `scripts/run_load_and_monitor.py`
(`reports/semana10/load_test_summary.json`, `locust_*_stats_history.csv`,
`docker_stats.csv`) para:
1. Estimar el costo por inferencia (USD / inferencia y USD / 1M inferencias) bajo
   múltiples topologías de nube (AWS ECS Fargate x86_64, Fargate ARM64 Graviton
   right-sized y GCP Cloud Run con facturación por uso).
2. Contrastar throughput observado y demanda supuesta para 470 estaciones
   con una ventana operativa de 19 horas al día.
3. Generar las 4 figuras de calidad editorial en `reports/figures/semana10_*.png`.
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

SEMANA10_DIR = Path("reports/semana10")
FIGURES_DIR = Path("reports/figures")

# Supuestos de demanda del escenario MiBici Guadalajara (AMG)
HOURS_PER_MONTH = 730.0
ACTIVE_HOURS_PER_DAY = 19.0  # Ventana supuesta 05:00 a 00:00; no acredita un horario oficial
ACTIVE_DAYS_PER_MONTH = 30.4
ACTIVE_HOURS_PER_MONTH = ACTIVE_HOURS_PER_DAY * ACTIVE_DAYS_PER_MONTH  # ~577.6 h/mes
MIBICI_STATIONS = 470

# Volúmenes de demanda operativa mensual (inferencias/mes)
# Escenario A: 1 predicción por estación cada 5 min durante 19h/día (monitoreo estándar CCO)
INFERENCES_MONTH_STD = int(MIBICI_STATIONS * (60 / 5) * ACTIVE_HOURS_PER_MONTH)   # ~3,257,664 / mes
# Escenario B: 1 predicción por estación cada 1 min durante 19h/día (monitoreo tiempo real + dashboard)
INFERENCES_MONTH_REALTIME = int(MIBICI_STATIONS * 60 * ACTIVE_HOURS_PER_MONTH)    # ~16,288,320 / mes
# Escenario C: Escalamiento metropolitano / alta frecuencia (50M inferencias/mes)
INFERENCES_MONTH_SCALE = 50_000_000


@dataclass(frozen=True)
class CloudProfile:
    """Tarifa pública de referencia (us-east-1 / us-central1, USD)."""

    key: str
    name: str
    short_label: str
    provider: str
    vcpu: float
    mem_gb: float
    hourly_usd: float
    billing_mode: str  # "always_on" | "scheduled_19h" | "serverless_per_req"
    notes: str


# Tarifas de referencia consultadas el 22 de noviembre de 2026 (AWS us-east-1 / GCP us-central1)
# - AWS ECS Fargate x86_64: $0.04048/vCPU-h + $0.004445/GB-h
# - AWS ECS Fargate ARM64 (Graviton): $0.03238/vCPU-h + $0.00356/GB-h
# - GCP Cloud Run (Tier 1, request-based): $0.00002400/vCPU-s + $0.00000250/GB-s + $0.40/1M requests
CLOUD_PROFILES = [
    CloudProfile(
        key="fargate_x86_baseline",
        name="AWS ECS Fargate x86_64 (1 vCPU, 2 GB — 24/7 sin optimizar)",
        short_label="Fargate x86\n1vCPU/2GB\n(24/7 Base)",
        provider="AWS",
        vcpu=1.0,
        mem_gb=2.0,
        hourly_usd=1.0 * 0.04048 + 2.0 * 0.004445,  # $0.04937/h
        billing_mode="always_on",
        notes="Referencia Fargate x86 de 1 vCPU y 2 GiB; Compose local limita cada servicio a 1 GiB.",
    ),
    CloudProfile(
        key="fargate_arm_rightsized",
        name="AWS ECS Fargate ARM64 Graviton (0.5 vCPU, 1 GB — 24/7 Right-sized)",
        short_label="Fargate ARM\n0.5vCPU/1GB\n(Right-sized)",
        provider="AWS",
        vcpu=0.5,
        mem_gb=1.0,
        hourly_usd=0.5 * 0.03238 + 1.0 * 0.00356,  # $0.01975/h
        billing_mode="always_on",
        notes="Ajuste de memoria/CPU guiado por docker stats + 20% ahorro arquitectura ARM64.",
    ),
    CloudProfile(
        key="fargate_arm_scheduled",
        name="AWS ECS Fargate ARM64 (0.5 vCPU, 1 GB — Auto-stop nocturno 19h/día)",
        short_label="Fargate ARM\n0.5vCPU/1GB\n(19h/día)",
        provider="AWS",
        vcpu=0.5,
        mem_gb=1.0,
        hourly_usd=0.5 * 0.03238 + 1.0 * 0.00356,  # $0.01975/h activo
        billing_mode="scheduled_19h",
        notes="Apagado programado 00:00-05:00 alineado al horario operativo de MiBici (-20.8% horas).",
    ),
    CloudProfile(
        key="cloudrun_serverless",
        name="GCP Cloud Run Serverless (1 vCPU, 512 MB — Scale-to-Zero por petición)",
        short_label="Cloud Run\n1vCPU/512MB\n(Serverless)",
        provider="GCP",
        vcpu=1.0,
        mem_gb=0.5,
        hourly_usd=0.0,
        billing_mode="serverless_per_req",
        notes="Escenario serial sin solapamiento, redondeo a 100 ms, sin nivel gratuito ni arranques en frío.",
    ),
]


def compute_profile_costs(
    profile: CloudProfile,
    monthly_inferences: int,
    avg_latency_ms: float,
    sustained_rps: float,
    mlflow_overhead_usd: float = 0.0,
) -> dict[str, Any]:
    """Proyecta una réplica por topología; su capacidad requiere benchmark propio.

    Cloud Run usa un escenario explícito sin solapamiento entre solicitudes.
    El redondeo por petición es aplicable a ese supuesto, no a tráfico con
    concurrencia compartida. No incluye nivel gratuito ni cold starts.
    """
    if monthly_inferences <= 0 or not all(math.isfinite(float(x)) for x in
            (avg_latency_ms, sustained_rps, mlflow_overhead_usd)):
        raise ValueError("Se requieren inferencias positivas y valores finitos")
    if avg_latency_ms <= 0 or sustained_rps <= 0 or mlflow_overhead_usd < 0:
        raise ValueError("Latencia y RPS deben ser positivos; costo adicional no negativo")
    replicas = 1  # Supuesto presupuestario; no certifica capacidad de otras CPU/arquitecturas.
    billed_seconds = None
    if profile.billing_mode == "always_on":
        compute_monthly = profile.hourly_usd * HOURS_PER_MONTH
    elif profile.billing_mode == "scheduled_19h":
        compute_monthly = profile.hourly_usd * ACTIVE_HOURS_PER_MONTH
    elif profile.billing_mode == "serverless_per_req":
        billed_seconds = math.ceil(avg_latency_ms / 100.0) * 0.1
        compute_monthly = monthly_inferences * (
            billed_seconds * (profile.vcpu * 0.00002400 + profile.mem_gb * 0.00000250)
            + 0.40 / 1_000_000.0
        )
    else:
        raise ValueError(f"Modo de facturación desconocido: {profile.billing_mode}")
    total = compute_monthly + mlflow_overhead_usd
    return {
        "key": profile.key, "name": profile.name, "short_label": profile.short_label,
        "provider": profile.provider, "vcpu": profile.vcpu, "mem_gb": profile.mem_gb,
        "replicas": replicas, "capacity_status": "requires_benchmark_per_topology",
        "required_operating_rps": monthly_inferences / (ACTIVE_HOURS_PER_MONTH * 3600),
        "monthly_inferences": monthly_inferences,
        "compute_monthly_usd": round(compute_monthly, 4),
        "mlflow_monthly_usd": round(mlflow_overhead_usd, 4),
        "total_monthly_usd": round(total, 4),
        "api_cost_per_1m_usd": compute_monthly / monthly_inferences * 1_000_000,
        "cost_per_1m_usd": round(total / monthly_inferences * 1_000_000, 4),
        "cost_per_inference_usd": total / monthly_inferences,
        "cloudrun_billed_seconds_per_request": billed_seconds,
        "notes": profile.notes,
    }


def generate_figures(summary: dict[str, Any], finops: dict[str, Any]) -> list[str]:
    """Genera las 4 figuras de alta resolución para el reporte oficial."""
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
            "axes.edgecolor": "#CBD5E1",
            "axes.linewidth": 0.8,
            "grid.color": "#E2E8F0",
            "grid.linestyle": "--",
            "grid.alpha": 0.7,
        }
    )

    scenarios = summary["scenarios"]
    users = [s["users"] for s in scenarios]
    rps_agg = [s["rps_aggregated"] for s in scenarios]
    rps_pred = [s["rps_predict"] for s in scenarios]
    p50 = [s["latency_p50_ms"] for s in scenarios]
    p95 = [s["latency_p95_ms"] for s in scenarios]
    p99 = [s["latency_p99_ms"] for s in scenarios]
    avg_lat = [s["latency_avg_ms"] for s in scenarios]
    err_rate = [s["error_rate_pct"] for s in scenarios]

    created: list[str] = []

    # --- Figura 1: Desempeño Locust por Escenario (RPS, Latencia Percentiles y Tasa de Error) ---
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11.5, 4.4), dpi=220)
    x = np.arange(len(users))
    w = 0.34
    b1 = ax1.bar(x - w / 2, rps_agg, width=w, color="#003366", label="RPS total API")
    b2 = ax1.bar(x + w / 2, rps_pred, width=w, color="#0284C7", label="Inferencias POST /predict")
    for bars in (b1, b2):
        for bar in bars:
            h = bar.get_height()
            ax1.text(bar.get_x() + bar.get_width() / 2, h + 1.5, f"{h:.1f}", ha="center", va="bottom", fontsize=8.5, fontweight="bold")
    ax1.set_xticks(x)
    ax1.set_xticklabels([f"{u} usuarios" for u in users], fontsize=9.5)
    ax1.set_ylabel("Peticiones por segundo (RPS)", fontsize=10, fontweight="bold", color="#0F172A")
    ax1.set_title("A) Throughput observado por concurrencia", fontsize=10.5, fontweight="bold", color="#003366", pad=10)
    ax1.set_ylim(0, max(rps_agg) * 1.22)
    ax1.grid(axis="y")
    ax1.legend(frameon=True, fontsize=8.5, loc="upper left")
    ax1.text(
        0.98, 0.05,
        f"Tasa de error observada: {max(err_rate):.2f}% en todos los escenarios",
        transform=ax1.transAxes, ha="right", va="bottom", fontsize=8.5,
        bbox={"boxstyle": "round,pad=0.35", "facecolor": "#ECFDF5", "edgecolor": "#10B981"},
        color="#065F46", fontweight="bold",
    )

    ax2.plot(users, p50, marker="o", linewidth=2.2, color="#10B981", label="p50 (Mediana)")
    ax2.plot(users, avg_lat, marker="s", linewidth=2.0, linestyle="--", color="#0284C7", label="Media")
    ax2.plot(users, p95, marker="^", linewidth=2.2, color="#F59E0B", label="p95")
    ax2.plot(users, p99, marker="D", linewidth=2.2, color="#DC2626", label="p99")
    for u, y50, y95, y99 in zip(users, p50, p95, p99):
        ax2.annotate(f"{y50:.0f}ms", (u, y50), textcoords="offset points", xytext=(0, -13), ha="center", fontsize=8, color="#047857")
        ax2.annotate(f"{y95:.0f}ms", (u, y95), textcoords="offset points", xytext=(0, 6), ha="center", fontsize=8, color="#B45309")
        ax2.annotate(f"{y99:.0f}ms", (u, y99), textcoords="offset points", xytext=(0, 7), ha="center", fontsize=8, color="#B91C1C", fontweight="bold")
    ax2.set_xticks(users)
    ax2.set_xticklabels([f"{u}u" for u in users], fontsize=9.5)
    ax2.set_xlabel("Usuarios concurrentes (Locust)", fontsize=10, fontweight="bold", color="#0F172A")
    ax2.set_ylabel("Latencia POST /predict (ms)", fontsize=10, fontweight="bold", color="#0F172A")
    ax2.set_title("B) Curva de Latencia (p50, Media, p95, p99)", fontsize=10.5, fontweight="bold", color="#003366", pad=10)
    ax2.set_ylim(0, max(p99) * 1.24)
    ax2.grid(True)
    ax2.legend(frameon=True, fontsize=8.5, loc="upper left")

    fig.suptitle("Pruebas de Carga con Locust — Microservicio MiBici Risk API (Contenedor Docker)", fontsize=12, fontweight="bold", color="#003366", y=1.01)
    fig.tight_layout()
    p1 = FIGURES_DIR / "semana10_locust_performance.png"
    fig.savefig(p1, bbox_inches="tight")
    plt.close(fig)
    created.append(str(p1))

    # --- Figura 2: Evolución Temporal (Serie de Tiempo RPS y p95 durante Estrés 100u) ---
    hist_path = SEMANA10_DIR / "locust_high_100u_stats_history.csv"
    if hist_path.exists():
        df_h = pd.read_csv(hist_path)
        df_h = df_h[df_h["Name"] == "Aggregated"].copy()
        if not df_h.empty:
            df_h["t_s"] = df_h["Timestamp"] - df_h["Timestamp"].iloc[0]
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10.8, 5.2), dpi=220, sharex=True)
            ax1.plot(df_h["t_s"], df_h["Requests/s"], color="#003366", linewidth=2.2, label="RPS total")
            ax1.fill_between(df_h["t_s"], df_h["Requests/s"], color="#BAE6FD", alpha=0.45)
            ax1.set_ylabel("Peticiones / seg", fontsize=9.5, fontweight="bold", color="#003366")
            ax1.set_title("Evolución Temporal en Carga alta observada (100 usuarios, 20 usuarios/s, 45 s)", fontsize=11, fontweight="bold", color="#003366", pad=8)
            ax1.grid(True)
            ax1_r = ax1.twinx()
            ax1_r.plot(df_h["t_s"], df_h["User Count"], color="#64748B", linestyle="--", linewidth=1.6, label="Usuarios activos")
            ax1_r.set_ylabel("Usuarios concurrentes", fontsize=9.5, color="#475569")
            lines1, labels1 = ax1.get_legend_handles_labels()
            lines2, labels2 = ax1_r.get_legend_handles_labels()
            ax1.legend(lines1 + lines2, labels1 + labels2, loc="lower right", fontsize=8.5)

            for col, color, lbl in [("50%", "#10B981", "p50 (ms)"), ("95%", "#F59E0B", "p95 (ms)"), ("99%", "#DC2626", "p99 (ms)")]:
                vals = pd.to_numeric(df_h[col], errors="coerce").fillna(0.0)
                ax2.plot(df_h["t_s"], vals, color=color, linewidth=2.0, label=lbl)
            ax2.set_xlabel("Tiempo transcurrido (segundos)", fontsize=9.5, fontweight="bold", color="#0F172A")
            ax2.set_ylabel("Latencia (ms)", fontsize=9.5, fontweight="bold", color="#0F172A")
            ax2.grid(True)
            ax2.legend(loc="upper left", fontsize=8.5, ncol=3)
            fig.tight_layout()
            p2 = FIGURES_DIR / "semana10_locust_timeseries.png"
            fig.savefig(p2, bbox_inches="tight")
            plt.close(fig)
            created.append(str(p2))

    # --- Figura 3: Monitoreo de Recursos de Contenedores (docker stats: CPU % y RAM MiB) ---
    docker_csv = SEMANA10_DIR / "docker_stats.csv"
    if docker_csv.exists():
        df_d = pd.read_csv(docker_csv)
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11.5, 4.4), dpi=220)
        x = np.arange(len(scenarios))
        w = 0.25

        api_cpu_avg = [s["api_resources"]["cpu_avg_perc"] for s in scenarios]
        api_cpu_max = [s["api_resources"]["cpu_max_perc"] for s in scenarios]
        mlf_cpu_avg = [s["mlflow_resources"]["cpu_avg_perc"] for s in scenarios]

        b1 = ax1.bar(x - w, api_cpu_avg, width=w, color="#0284C7", label="API CPU Media (%)")
        b2 = ax1.bar(x, api_cpu_max, width=w, color="#003366", label="API CPU Pico (%)")
        b3 = ax1.bar(x + w, mlf_cpu_avg, width=w, color="#94A3B8", label="MLflow CPU Media (%)")
        for bars in (b1, b2, b3):
            for bar in bars:
                h = bar.get_height()
                ax1.text(bar.get_x() + bar.get_width() / 2, h + 1.5, f"{h:.1f}%", ha="center", va="bottom", fontsize=7.8, fontweight="bold")
        ax1.axhline(100.0, color="#DC2626", linestyle=":", linewidth=1.4, label="Límite configurado (1.0 vCPU = 100%)")
        ax1.set_xticks(x)
        ax1.set_xticklabels([f"{u} usuarios" for u in users], fontsize=9.5)
        ax1.set_ylabel("Uso de CPU (%)", fontsize=10, fontweight="bold", color="#0F172A")
        ax1.set_title("A) Consumo de CPU por Contenedor (docker stats)", fontsize=10.5, fontweight="bold", color="#003366", pad=10)
        ax1.set_ylim(0, max(max(api_cpu_max), 105.0) * 1.18)
        ax1.grid(axis="y")
        ax1.legend(fontsize=8, loc="upper left")

        api_mem_max = [s["api_resources"]["mem_max_mib"] for s in scenarios]
        mlf_mem_max = [s["mlflow_resources"]["mem_max_mib"] for s in scenarios]
        b4 = ax2.bar(x - w / 2, api_mem_max, width=w * 1.2, color="#0D9488", label="API RAM Pico (MiB)")
        b5 = ax2.bar(x + w / 2, mlf_mem_max, width=w * 1.2, color="#6366F1", label="MLflow RAM Pico (MiB)")
        for bars in (b4, b5):
            for bar in bars:
                h = bar.get_height()
                ax2.text(bar.get_x() + bar.get_width() / 2, h + 12, f"{h:.0f}", ha="center", va="bottom", fontsize=8.2, fontweight="bold")
        ax2.axhline(1024.0, color="#DC2626", linestyle=":", linewidth=1.4, label="Límite Compose (1024 MiB)")
        ax2.set_xticks(x)
        ax2.set_xticklabels([f"{u} usuarios" for u in users], fontsize=9.5)
        ax2.set_ylabel("Memoria RAM (MiB)", fontsize=10, fontweight="bold", color="#0F172A")
        ax2.set_title("B) Huella de Memoria RAM por Contenedor", fontsize=10.5, fontweight="bold", color="#003366", pad=10)
        ax2.set_ylim(0, max(max(api_mem_max + mlf_mem_max), 1050.0) * 1.15)
        ax2.grid(axis="y")
        ax2.legend(fontsize=8, loc="upper right")

        fig.suptitle("Monitoreo de Recursos de Contenedores durante Pruebas de Carga (Docker Compose)", fontsize=12, fontweight="bold", color="#003366", y=1.01)
        fig.tight_layout()
        p3 = FIGURES_DIR / "semana10_docker_stats.png"
        fig.savefig(p3, bbox_inches="tight")
        plt.close(fig)
        created.append(str(p3))

    # --- Figura 4: Análisis FinOps — Costo Mensual y Costo por 1M Inferencias ---
    rt_rows = finops["workloads"]["realtime_1min"]["profiles"]
    std_rows = finops["workloads"]["standard_5min"]["profiles"]
    labels = [r["short_label"] for r in rt_rows]
    rt_cost_1m = [r["cost_per_1m_usd"] for r in rt_rows]
    std_cost_1m = [r["cost_per_1m_usd"] for r in std_rows]
    rt_monthly = [r["total_monthly_usd"] for r in rt_rows]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11.8, 4.6), dpi=220)
    x = np.arange(len(labels))
    w = 0.36
    b1 = ax1.bar(x - w / 2, std_cost_1m, width=w, color="#94A3B8", label="Estándar CCO (3.26M inf/mes)")
    b2 = ax1.bar(x + w / 2, rt_cost_1m, width=w, color="#003366", label="Tiempo Real 1-min (16.29M inf/mes)")
    for bars in (b1, b2):
        for bar in bars:
            h = bar.get_height()
            ax1.text(bar.get_x() + bar.get_width() / 2, h + 0.15, f"${h:.2f}", ha="center", va="bottom", fontsize=7.8, fontweight="bold")
    ax1.set_xticks(x)
    ax1.set_xticklabels(labels, fontsize=8.2)
    ax1.set_ylabel("USD por 1,000,000 inferencias", fontsize=9.5, fontweight="bold", color="#0F172A")
    ax1.set_title("A) Costo Efectivo por Millón de Inferencias", fontsize=10.5, fontweight="bold", color="#003366", pad=10)
    ax1.set_ylim(0, max(std_cost_1m + rt_cost_1m) * 1.22)
    ax1.grid(axis="y")
    ax1.legend(fontsize=8.2, loc="upper right")

    colors = ["#DC2626", "#0284C7", "#10B981", "#6366F1", "#F59E0B"]
    b3 = ax2.bar(x, rt_monthly, width=0.52, color=colors)
    base_cost = rt_monthly[0]
    for bar, val in zip(b3, rt_monthly):
        savings = (1.0 - val / base_cost) * 100.0 if base_cost > 0 else 0.0
        tag = f"${val:.2f}\n({-savings:+.0f}%)" if abs(savings) > 1.0 else f"${val:.2f}\n(Base)"
        ax2.text(bar.get_x() + bar.get_width() / 2, val + 0.6, tag, ha="center", va="bottom", fontsize=8.0, fontweight="bold")
    ax2.set_xticks(x)
    ax2.set_xticklabels(labels, fontsize=8.2)
    ax2.set_ylabel("API y presupuesto MLflow (USD/mes)", fontsize=9.5, fontweight="bold", color="#0F172A")
    ax2.set_title("B) Ahorro FinOps Mensual (Escenario Tiempo Real 16.3M)", fontsize=10.5, fontweight="bold", color="#003366", pad=10)
    ax2.set_ylim(0, max(rt_monthly) * 1.28)
    ax2.grid(axis="y")

    fig.suptitle("Análisis FinOps — Proyección de costo con presupuesto MLflow y una réplica por topología", fontsize=12, fontweight="bold", color="#003366", y=1.01)
    fig.tight_layout()
    p4 = FIGURES_DIR / "semana10_finops_costs.png"
    fig.savefig(p4, bbox_inches="tight")
    plt.close(fig)
    created.append(str(p4))

    return created


def run_finops_analysis(
    summary_path: Path = SEMANA10_DIR / "load_test_summary.json",
    mlflow_overhead_usd: float = 36.0401,
) -> dict[str, Any]:
    """Ejecuta el análisis FinOps completo a partir de los resultados reales de carga."""
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    scenarios = summary["scenarios"]

    # Métricas observadas de referencia (usamos carga alta 100u para capacidad sostenida)
    if summary.get("overall_status") not in (None, "PASS"):
        raise ValueError("FinOps requiere una corrida de carga aprobada")
    if any(s.get("failure_count", 0) or s.get("status") == "FAIL" for s in scenarios):
        raise ValueError("La corrida contiene fallos")
    peak_sc = max(scenarios, key=lambda s: s["rps_predict"])
    mid_sc = scenarios[1] if len(scenarios) > 1 else peak_sc

    sustained_rps = float(peak_sc["rps_predict"])
    avg_latency_ms = float(mid_sc["latency_avg_ms"])
    peak_api_cpu = max(s["api_resources"]["cpu_max_perc"] for s in scenarios)
    peak_api_mem_mib = max(s["api_resources"]["mem_max_mib"] for s in scenarios)
    peak_mlflow_mem_mib = max(s["mlflow_resources"]["mem_max_mib"] for s in scenarios)

    workloads = {}
    for w_key, w_label, n_inf in [
        ("standard_5min", "Monitoreo CCO Estándar (470 est. c/5 min, 19h/día)", INFERENCES_MONTH_STD),
        ("realtime_1min", "Monitoreo Tiempo Real (470 est. c/1 min, 19h/día)", INFERENCES_MONTH_REALTIME),
        ("high_scale_50m", "Escalamiento Metropolitano (50M inferencias/mes)", INFERENCES_MONTH_SCALE),
    ]:
        rows = [
            compute_profile_costs(
                profile=p,
                monthly_inferences=n_inf,
                avg_latency_ms=avg_latency_ms,
                sustained_rps=sustained_rps,
                mlflow_overhead_usd=mlflow_overhead_usd,
            )
            for p in CLOUD_PROFILES
        ]
        workloads[w_key] = {
            "label": w_label,
            "monthly_inferences": n_inf,
            "profiles": rows,
        }

    baseline_rt = workloads["realtime_1min"]["profiles"][0]
    best_always_on = workloads["realtime_1min"]["profiles"][2]  # Fargate ARM 19h/día
    best_serverless = workloads["realtime_1min"]["profiles"][-1]  # Cloud Run

    finops = {
        "observed_telemetry": {
            "sustained_rps_peak": sustained_rps,
            "avg_latency_ms_nominal": avg_latency_ms,
            "peak_api_cpu_perc": peak_api_cpu,
            "peak_api_mem_mib": peak_api_mem_mib,
            "peak_mlflow_mem_mib": peak_mlflow_mem_mib,
            "extrapolated_inferences_month_730h": int(sustained_rps * 3600.0 * HOURS_PER_MONTH),
            "rps_total_peak": float(peak_sc["rps_aggregated"]),
            "capacity_scope": "observed_mixed_workload_not_maximum_capacity",
            "historical_model_provenance": summary.get("model_before") or "not_recorded",
        },
        "assumptions": {
            "pricing_reference_date": "2026-11-22",
            "sources": ["https://aws.amazon.com/fargate/pricing/", "https://cloud.google.com/run/pricing"],
            "hours_per_month": HOURS_PER_MONTH,
            "operating_hours_per_month": ACTIVE_HOURS_PER_MONTH,
            "mlflow_monthly_usd": mlflow_overhead_usd,
            "mlflow_budget_basis": "Una tarea x86 1 vCPU 2 GiB, 730 h; presupuesto de referencia",
            "cloudrun_scope": "Peticiones aisladas con redondeo a 100 ms; sin nivel gratuito, solapamiento ni cold starts",
            "excluded_costs": ["storage", "logs", "network", "load_balancer", "IPv4", "taxes", "training"],
            "profile_capacity": "Una réplica supuesta; validar cada topología con carga antes de desplegar",
            "ec2_savings_price": "Omitido: falta cotización verificable por plazo y modalidad de pago",
        },
        "workloads": workloads,
        "key_findings": {
            "baseline_monthly_usd": baseline_rt["total_monthly_usd"],
            "baseline_cost_per_1m_usd": baseline_rt["cost_per_1m_usd"],
            "optimized_scheduled_arm_monthly_usd": best_always_on["total_monthly_usd"],
            "optimized_scheduled_arm_savings_pct": round(
                (1.0 - best_always_on["total_monthly_usd"] / baseline_rt["total_monthly_usd"]) * 100.0, 1
            ),
            "serverless_std_monthly_usd": workloads["standard_5min"]["profiles"][-1]["total_monthly_usd"],
            "serverless_std_savings_pct": round(
                (
                    1.0
                    - workloads["standard_5min"]["profiles"][-1]["total_monthly_usd"]
                    / workloads["standard_5min"]["profiles"][0]["total_monthly_usd"]
                )
                * 100.0,
                1,
            ),
            "serverless_rt_monthly_usd": best_serverless["total_monthly_usd"],
        },
        "cloud_profiles_catalog": [asdict(p) for p in CLOUD_PROFILES],
    }

    out_path = SEMANA10_DIR / "finops_summary.json"
    out_path.write_text(json.dumps(finops, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    figs = generate_figures(summary, finops)
    print(f"✓ Análisis FinOps guardado en {out_path}")
    for f in figs:
        print(f"✓ Figura generada: {f}")
    return finops


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary", type=Path, default=SEMANA10_DIR / "load_test_summary.json")
    parser.add_argument("--mlflow-monthly-usd", type=float, default=36.0401)
    args = parser.parse_args()
    run_finops_analysis(args.summary, args.mlflow_monthly_usd)
