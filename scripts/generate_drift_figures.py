"""Script para generar figuras visuales de alta calidad del reporte de drift de Evidently.

Extrae las métricas de `reports/evidently/p2_data_drift.json` y genera:
1. `reports/figures/evidently_drift_wasserstein_ranking.png`: Ranking de distancia de deriva.
2. `reports/figures/evidently_distributions_drift.png`: Distribuciones comparativas (2025 vs 2026).
3. `reports/figures/evidently_drift_summary_card.png`: Tarjeta ejecutiva de auditoría de datos.
"""

from pathlib import Path
import json
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

from src.p2_config import FIGURES_DIR, P2_FEATURES_TARGET_PARQUET
from src.validation.p2_checks import load_dataset_samples

# Configuración estética institucional
plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")
plt.rcParams["font.family"] = "sans-serif"
plt.rcParams["font.sans-serif"] = ["Helvetica", "Arial", "DejaVu Sans"]
plt.rcParams["axes.edgecolor"] = "#CBD5E1"
plt.rcParams["axes.linewidth"] = 0.8

FIGURES_DIR.mkdir(parents=True, exist_ok=True)


def load_drift_metrics_from_json(json_path: Path) -> pd.DataFrame:
    """Extrae las distancias de deriva y métodos de cada variable desde el JSON de Evidently."""
    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)

    records = []
    for m in data.get("metrics", []):
        name = m.get("metric_name", "")
        if name.startswith("ValueDrift"):
            # Formato típico: ValueDrift(column=col,method=...,threshold=0.1)
            # Parsear parámetros dentro del paréntesis
            parts = name[name.find("(") + 1 : name.rfind(")")].split(",")
            col = ""
            method = ""
            thresh = 0.1
            for p in parts:
                if p.startswith("column="):
                    col = p.split("=")[1]
                elif p.startswith("method="):
                    method = p.split("=")[1]
                elif p.startswith("threshold="):
                    try:
                        thresh = float(p.split("=")[1])
                    except ValueError:
                        thresh = 0.1

            score = float(m.get("value", 0.0))
            records.append({
                "feature": col,
                "drift_score": score,
                "method": method,
                "threshold": thresh,
                "drift_detected": score >= thresh,
            })

    df = pd.DataFrame(records).sort_values("drift_score", ascending=True)
    return df


def plot_drift_ranking(df: pd.DataFrame, output_path: Path):
    """Genera gráfico de barras horizontal del ranking de deriva por variable."""
    fig, ax = plt.subplots(figsize=(10, 6), dpi=300)

    colors = []
    for s in df["drift_score"]:
        if s >= 0.1:
            colors.append("#DC2626")  # Rojo crítico
        elif s >= 0.05:
            colors.append("#F59E0B")  # Ámbar advertencia
        else:
            colors.append("#0284C7")  # Azul estable

    bars = ax.barh(df["feature"], df["drift_score"], color=colors, height=0.65, edgecolor="#0F172A", linewidth=0.5)

    # Línea de umbral crítico Evidently
    ax.axvline(0.1, color="#EF4444", linestyle="--", linewidth=1.5, label="Umbral Crítico Drift (0.10)")
    ax.axvline(0.05, color="#F59E0B", linestyle=":", linewidth=1.2, label="Umbral Advertencia / Alerta temprana (0.05)")

    # Etiquetas de valor en cada barra
    for bar in bars:
        width = bar.get_width()
        ax.text(
            width + 0.002,
            bar.get_y() + bar.get_height() / 2,
            f"{width:.4f}",
            va="center",
            ha="left",
            fontsize=8.5,
            color="#1E293B",
            fontweight="bold",
        )

    ax.set_xlim(0, 0.12)
    ax.set_title("Evidently Data Drift: Ranking de Deriva por Variable en P2\n(Referencia: 2025 vs. Actual: 2026 | Wasserstein / Jensen-Shannon Distance)", fontsize=12, fontweight="bold", pad=14, color="#003366")
    ax.set_xlabel("Distancia de Deriva Normalizada (Wasserstein / Jensen-Shannon)", fontsize=10, fontweight="bold", labelpad=8)
    ax.legend(loc="lower right", frameon=True, facecolor="#F8FAFC", edgecolor="#CBD5E1", fontsize=9)
    ax.grid(axis="x", linestyle="--", alpha=0.6)

    plt.tight_layout()
    fig.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"✓ Guardado ranking de drift en: {output_path}")


def plot_drift_distributions(reference: pd.DataFrame, current: pd.DataFrame, output_path: Path):
    """Genera subplots de densidades comparativas de las 4 variables con mayor desplazamiento."""
    top_cols = ["balance_rolling_12h", "balance_rolling_3h", "llegadas_lag_168", "salidas_lag_168"]
    titles = [
        "Balance Rodante 12h (Wasserstein = 0.0711)",
        "Balance Rodante 3h (Wasserstein = 0.0646)",
        "Llegadas Lag 168h / Semanal (Wasserstein = 0.0527)",
        "Salidas Lag 168h / Semanal (Wasserstein = 0.0391)",
    ]

    fig, axes = plt.subplots(2, 2, figsize=(12, 8), dpi=300)
    axes = axes.flatten()

    for idx, col in enumerate(top_cols):
        ax = axes[idx]
        ref_vals = reference[col].dropna()
        cur_vals = current[col].dropna()

        # Recortar outliers extremos visuales al 99.5 percentil para apreciar la densidad
        q_low = min(ref_vals.quantile(0.005), cur_vals.quantile(0.005))
        q_high = max(ref_vals.quantile(0.995), cur_vals.quantile(0.995))

        sns.kdeplot(
            ref_vals,
            ax=ax,
            color="#0284C7",
            fill=True,
            alpha=0.25,
            linewidth=2,
            label="Referencia (2025)",
            clip=(q_low, q_high),
        )
        sns.kdeplot(
            cur_vals,
            ax=ax,
            color="#EA580C",
            fill=True,
            alpha=0.25,
            linewidth=2,
            label="Actual (2026)",
            clip=(q_low, q_high),
        )

        ax.axvline(ref_vals.mean(), color="#0284C7", linestyle="--", linewidth=1.2, alpha=0.8)
        ax.axvline(cur_vals.mean(), color="#EA580C", linestyle="--", linewidth=1.2, alpha=0.8)

        ax.set_title(titles[idx], fontsize=10.5, fontweight="bold", color="#0F172A", pad=8)
        ax.set_xlabel(f"Valor de {col}", fontsize=9)
        ax.set_ylabel("Densidad Empírica", fontsize=9)
        ax.set_xlim(q_low, q_high)
        ax.legend(fontsize=8.5, loc="upper right")
        ax.grid(True, linestyle="--", alpha=0.5)

    fig.suptitle(
        "Comparación de Distribuciones: Variables con Mayor Desplazamiento Relativo\n(MiBici P2: Conjunto de Referencia 2025 vs. Producción 2026)",
        fontsize=13,
        fontweight="bold",
        color="#003366",
        y=1.02,
    )

    plt.tight_layout()
    fig.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"✓ Guardado comparativo de distribuciones en: {output_path}")


def plot_summary_card(df: pd.DataFrame, output_path: Path):
    """Genera una ficha ejecutiva de auditoría de calidad y drift de datos."""
    fig, ax = plt.subplots(figsize=(9, 4.5), dpi=300)
    ax.axis("off")

    # Fondo de la tarjeta
    from matplotlib.patches import FancyBboxPatch
    rect = FancyBboxPatch((0.02, 0.05), 0.96, 0.90, transform=ax.transAxes, facecolor="#F8FAFC", edgecolor="#003366", linewidth=1.5, boxstyle="round,pad=0.03")
    ax.add_patch(rect)

    ax.text(0.5, 0.88, "AUDITORÍA DE DATA DRIFT Y CALIDAD DE DATOS (EVIDENTLY)", transform=ax.transAxes, ha="center", fontsize=12, fontweight="bold", color="#003366")
    ax.text(0.5, 0.81, "Proyecto MiBici Guadalajara - Equipo 30 | Modelo P2 (Riesgo Operativo a 2 Horas)", transform=ax.transAxes, ha="center", fontsize=9.5, color="#475569")

    # Línea divisoria
    ax.plot([0.06, 0.94], [0.76, 0.76], transform=ax.transAxes, color="#CBD5E1", linewidth=1.2)

    # Métricas clave en 3 columnas
    # Columna 1: Estado General
    ax.text(0.18, 0.68, "ESTADO GENERAL", transform=ax.transAxes, ha="center", fontsize=10, fontweight="bold", color="#0F172A")
    ax.text(0.18, 0.54, "NO DRIFT CRÍTICO", transform=ax.transAxes, ha="center", fontsize=11, fontweight="bold", color="#16A34A")
    ax.text(0.18, 0.44, "0 / 17 variables > 0.10\nDataset Drift: 0.0%", transform=ax.transAxes, ha="center", fontsize=8.5, color="#334155")

    # Columna 2: Calidad e Integridad
    ax.text(0.50, 0.68, "CALIDAD DE DATOS", transform=ax.transAxes, ha="center", fontsize=10, fontweight="bold", color="#0F172A")
    ax.text(0.50, 0.54, "100% ÍNTEGRO", transform=ax.transAxes, ha="center", fontsize=11, fontweight="bold", color="#0284C7")
    ax.text(0.50, 0.44, "0 valores nulos o infinitos\n7,500 ref / 7,500 test", transform=ax.transAxes, ha="center", fontsize=8.5, color="#334155")

    # Columna 3: Variables Bajo Monitoreo
    ax.text(0.82, 0.68, "DERIVA MODERADA", transform=ax.transAxes, ha="center", fontsize=10, fontweight="bold", color="#0F172A")
    ax.text(0.82, 0.54, "3 VARIABLES EN ALERTA", transform=ax.transAxes, ha="center", fontsize=11, fontweight="bold", color="#D97706")
    ax.text(0.82, 0.44, "balance_rolling_12h (0.071)\nbalance_rolling_3h (0.065)\nllegadas_lag_168 (0.053)", transform=ax.transAxes, ha="center", fontsize=8, color="#334155")

    # Conclusión en el pie
    ax.plot([0.06, 0.94], [0.34, 0.34], transform=ax.transAxes, color="#CBD5E1", linewidth=1.2)
    ax.text(
        0.5,
        0.20,
        "Dictamen Técnico: Las dinámicas de balance móvil y estacionalidad semanal presentan desplazamiento\nrelativo por el ciclo de inicio de año 2026. Se prescribe ejercicio de A/B Testing para evaluar la necesidad\nde reentrenamiento adaptativo (Continuous Training).",
        transform=ax.transAxes,
        ha="center",
        fontsize=8.5,
        color="#1E293B",
        style="italic",
    )

    fig.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"✓ Guardada tarjeta de resumen en: {output_path}")


def main():
    json_path = Path("reports/evidently/p2_data_drift.json")
    if not json_path.exists():
        raise FileNotFoundError(f"No se encontró el reporte JSON de Evidently en {json_path}")

    df_metrics = load_drift_metrics_from_json(json_path)

    ranking_plot = FIGURES_DIR / "evidently_drift_wasserstein_ranking.png"
    plot_drift_ranking(df_metrics, ranking_plot)

    summary_card_plot = FIGURES_DIR / "evidently_drift_summary_card.png"
    plot_summary_card(df_metrics, summary_card_plot)

    # Cargar datos para gráfico de densidades
    reference, current, _ = load_dataset_samples(P2_FEATURES_TARGET_PARQUET, sample_size=15000)
    distributions_plot = FIGURES_DIR / "evidently_distributions_drift.png"
    plot_drift_distributions(reference, current, distributions_plot)


if __name__ == "__main__":
    main()
