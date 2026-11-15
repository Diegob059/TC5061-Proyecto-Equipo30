"""Módulo de A/B Testing para comparación de versiones registradas en MLflow (P2 Riesgo).

Compara metodológicamente la Versión 1 (Champion) y la Versión 2 (Challenger)
del modelo `mibici-equipo30-p2-riesgo` sobre el conjunto de evaluación del periodo
actual (producción 2026).
"""

import json
import time
from pathlib import Path
from typing import Any, Dict, Tuple

import matplotlib.pyplot as plt
import mlflow
import numpy as np
import pandas as pd
import seaborn as sns
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    fbeta_score,
    log_loss,
    precision_score,
    recall_score,
)

from src.p2_config import FIGURES_DIR, MLFLOW_TRACKING_URI, P2_REPORTS_DIR, logger


def evaluate_predictions(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    y_proba: np.ndarray | None = None,
    latency_ms_per_1k: float = 0.0,
) -> Dict[str, float]:
    """Calcula métricas detalladas de desempeño global y por clase."""
    metrics = {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "balanced_accuracy": float(balanced_accuracy_score(y_true, y_pred)),
        "macro_f1": float(f1_score(y_true, y_pred, average="macro", zero_division=0)),
        "weighted_f1": float(f1_score(y_true, y_pred, average="weighted", zero_division=0)),
        # Clase 0: Normal
        "recall_normal": float(recall_score(y_true, y_pred, labels=[0], average="micro", zero_division=0)),
        "precision_normal": float(precision_score(y_true, y_pred, labels=[0], average="micro", zero_division=0)),
        "f1_normal": float(f1_score(y_true, y_pred, labels=[0], average="micro", zero_division=0)),
        # Clase 1: Desabasto (vacío) - Crítica
        "recall_desabasto": float(recall_score(y_true, y_pred, labels=[1], average="micro", zero_division=0)),
        "precision_desabasto": float(precision_score(y_true, y_pred, labels=[1], average="micro", zero_division=0)),
        "f1_desabasto": float(f1_score(y_true, y_pred, labels=[1], average="micro", zero_division=0)),
        "f2_desabasto": float(fbeta_score(y_true, y_pred, beta=2, labels=[1], average="micro", zero_division=0)),
        # Clase 2: Saturación (lleno)
        "recall_saturacion": float(recall_score(y_true, y_pred, labels=[2], average="micro", zero_division=0)),
        "precision_saturacion": float(precision_score(y_true, y_pred, labels=[2], average="micro", zero_division=0)),
        "f1_saturacion": float(f1_score(y_true, y_pred, labels=[2], average="micro", zero_division=0)),
        "f2_saturacion": float(fbeta_score(y_true, y_pred, beta=2, labels=[2], average="micro", zero_division=0)),
        "latency_ms_per_1k": float(latency_ms_per_1k),
    }

    if y_proba is not None:
        try:
            metrics["log_loss"] = float(log_loss(y_true, y_proba, labels=[0, 1, 2]))
            # Brier Score multiclase (promedio sobre one-hot)
            y_one_hot = np.eye(3)[y_true]
            brier = np.mean(np.sum((y_proba - y_one_hot) ** 2, axis=1))
            metrics["brier_score"] = float(brier)
        except Exception as e:
            logger.warning(f"Aviso al calcular métricas probabilísticas: {e}")

    return metrics


def mcnemar_test(y_true: np.ndarray, y_pred_a: np.ndarray, y_pred_b: np.ndarray) -> Dict[str, Any]:
    """Ejecuta la prueba estadística de McNemar para contraste de clasificadores dependientes."""
    correct_a = y_pred_a == y_true
    correct_b = y_pred_b == y_true

    # Tabla de contingencia 2x2
    # n00: ambos incorrectos, n01: A incorrecto, B correcto
    # n10: A correcto, B incorrecto, n11: ambos correctos
    n00 = int(np.sum((~correct_a) & (~correct_b)))
    n01 = int(np.sum((~correct_a) & (correct_b)))
    n10 = int(np.sum((correct_a) & (~correct_b)))
    n11 = int(np.sum((correct_a) & (correct_b)))

    # Estadístico con corrección de continuidad de Edwards
    discordant = n01 + n10
    if discordant == 0:
        statistic = 0.0
        p_value = 1.0
    else:
        statistic = float(((abs(n01 - n10) - 1.0) ** 2) / discordant)
        from scipy.stats import chi2
        p_value = float(1.0 - chi2.cdf(statistic, df=1))

    return {
        "contingency_table": {"n00": n00, "n01": n01, "n10": n10, "n11": n11},
        "discordant_pairs": discordant,
        "mcnemar_statistic": statistic,
        "p_value": p_value,
        "is_significant_at_05": p_value < 0.05,
    }


def bootstrap_metric_difference(
    y_true: np.ndarray,
    y_pred_a: np.ndarray,
    y_pred_b: np.ndarray,
    n_bootstrap: int = 500,
    seed: int = 42,
) -> Dict[str, Dict[str, float]]:
    """Calcula intervalos de confianza bootstrap al 95% para las diferencias de métricas (B - A)."""
    rng = np.random.default_rng(seed)
    n = len(y_true)

    diffs_macro_f1 = []
    diffs_recall_desabasto = []
    diffs_recall_saturacion = []
    diffs_balanced_acc = []

    for _ in range(n_bootstrap):
        idx = rng.integers(0, n, size=n)
        yt_boot = y_true[idx]
        ya_boot = y_pred_a[idx]
        yb_boot = y_pred_b[idx]

        f1_a = f1_score(yt_boot, ya_boot, average="macro", zero_division=0)
        f1_b = f1_score(yt_boot, yb_boot, average="macro", zero_division=0)
        diffs_macro_f1.append(f1_b - f1_a)

        rec_des_a = recall_score(yt_boot, ya_boot, labels=[1], average="micro", zero_division=0)
        rec_des_b = recall_score(yt_boot, yb_boot, labels=[1], average="micro", zero_division=0)
        diffs_recall_desabasto.append(rec_des_b - rec_des_a)

        rec_sat_a = recall_score(yt_boot, ya_boot, labels=[2], average="micro", zero_division=0)
        rec_sat_b = recall_score(yt_boot, yb_boot, labels=[2], average="micro", zero_division=0)
        diffs_recall_saturacion.append(rec_sat_b - rec_sat_a)

        ba_a = balanced_accuracy_score(yt_boot, ya_boot)
        ba_b = balanced_accuracy_score(yt_boot, yb_boot)
        diffs_balanced_acc.append(ba_b - ba_a)

    def _summary(diffs):
        return {
            "mean_difference": float(np.mean(diffs)),
            "ci_95_low": float(np.percentile(diffs, 2.5)),
            "ci_95_high": float(np.percentile(diffs, 97.5)),
        }

    return {
        "macro_f1": _summary(diffs_macro_f1),
        "recall_desabasto": _summary(diffs_recall_desabasto),
        "recall_saturacion": _summary(diffs_recall_saturacion),
        "balanced_accuracy": _summary(diffs_balanced_acc),
    }


def plot_ab_comparison_figures(
    metrics_a: Dict[str, float],
    metrics_b: Dict[str, float],
    cm_a: np.ndarray,
    cm_b: np.ndarray,
    output_bars_path: Path,
    output_cm_path: Path,
):
    """Genera visualizaciones de alta calidad de métricas comparativas y matrices de confusión."""
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Gráfico de barras comparativo de métricas clave
    metric_keys = [
        ("balanced_accuracy", "Balanced Accuracy"),
        ("macro_f1", "Macro F1-Score"),
        ("recall_desabasto", "Recall Desabasto (C1)"),
        ("recall_saturacion", "Recall Saturación (C2)"),
        ("precision_desabasto", "Prec. Desabasto (C1)"),
        ("precision_saturacion", "Prec. Saturación (C2)"),
    ]

    labels = [m[1] for m in metric_keys]
    vals_a = [metrics_a.get(m[0], 0.0) for m in metric_keys]
    vals_b = [metrics_b.get(m[0], 0.0) for m in metric_keys]

    x = np.arange(len(labels))
    width = 0.35

    fig, ax = plt.subplots(figsize=(11, 6), dpi=300)
    rects1 = ax.bar(x - width / 2, vals_a, width, label="Versión 1 Champion (@champion)", color="#0284C7", edgecolor="#0F172A", linewidth=0.6)
    rects2 = ax.bar(x + width / 2, vals_b, width, label="Versión 2 Challenger (@challenger)", color="#10B981", edgecolor="#0F172A", linewidth=0.6)

    ax.set_title("A/B Testing: Comparación de Métricas Clave en Producción (2026)\nVersión 1 Champion (lgbm_profundo) vs. Versión 2 Challenger (lgbm_challenger_v2)", fontsize=11.5, fontweight="bold", pad=12, color="#003366")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=15, ha="right", fontsize=9.5)
    ax.set_ylabel("Valor de la Métrica (0.0 - 1.0)", fontsize=10, fontweight="bold")
    ax.set_ylim(0, 1.05)
    ax.legend(frameon=True, facecolor="#F8FAFC", edgecolor="#CBD5E1", fontsize=9.5, loc="lower right")
    ax.grid(axis="y", linestyle="--", alpha=0.5)

    # Anotar valores sobre las barras
    for rect in rects1:
        h = rect.get_height()
        ax.annotate(f"{h:.3f}", xy=(rect.get_x() + rect.get_width() / 2, h), xytext=(0, 3), textcoords="offset points", ha="center", va="bottom", fontsize=8, color="#0284C7", fontweight="bold")

    for rect in rects2:
        h = rect.get_height()
        ax.annotate(f"{h:.3f}", xy=(rect.get_x() + rect.get_width() / 2, h), xytext=(0, 3), textcoords="offset points", ha="center", va="bottom", fontsize=8, color="#047857", fontweight="bold")

    plt.tight_layout()
    fig.savefig(output_bars_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    logger.info(f"✓ Guardado gráfico de barras A/B en: {output_bars_path}")

    # 2. Matrices de confusión normalizadas lado a lado
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5.5), dpi=300)
    class_names = ["Normal (0)", "Desabasto (1)", "Saturación (2)"]

    # Normalizar por fila (recall real)
    cm_a_norm = cm_a.astype("float") / cm_a.sum(axis=1)[:, np.newaxis]
    cm_b_norm = cm_b.astype("float") / cm_b.sum(axis=1)[:, np.newaxis]

    sns.heatmap(cm_a_norm, annot=True, fmt=".2%", cmap="Blues", cbar=False, ax=ax1, xticklabels=class_names, yticklabels=class_names)
    ax1.set_title(f"Versión 1 Champion (@champion)\nBalanced Acc: {metrics_a['balanced_accuracy']:.2%} | Macro F1: {metrics_a['macro_f1']:.3f}", fontsize=10, fontweight="bold", color="#003366")
    ax1.set_ylabel("Clase Verdadera (Ground Truth)", fontsize=9.5)
    ax1.set_xlabel("Clase Predicha", fontsize=9.5)

    sns.heatmap(cm_b_norm, annot=True, fmt=".2%", cmap="Greens", cbar=False, ax=ax2, xticklabels=class_names, yticklabels=class_names)
    ax2.set_title(f"Versión 2 Challenger (@challenger)\nBalanced Acc: {metrics_b['balanced_accuracy']:.2%} | Macro F1: {metrics_b['macro_f1']:.3f}", fontsize=10, fontweight="bold", color="#003366")
    ax2.set_ylabel("Clase Verdadera (Ground Truth)", fontsize=9.5)
    ax2.set_xlabel("Clase Predicha", fontsize=9.5)

    fig.suptitle("Matrices de Confusión Normalizadas en Conjunto de Producción 2026", fontsize=12, fontweight="bold", color="#0F172A", y=1.02)
    plt.tight_layout()
    fig.savefig(output_cm_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    logger.info(f"✓ Guardadas matrices de confusión A/B en: {output_cm_path}")
