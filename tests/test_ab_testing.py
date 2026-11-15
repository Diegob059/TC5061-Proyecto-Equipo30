"""Pruebas unitarias para la suite de A/B Testing (Pregunta 2 - Riesgo)."""

import numpy as np
import pytest

from src.models.p2_ab_test import (
    bootstrap_metric_difference,
    evaluate_predictions,
    mcnemar_test,
)


def test_evaluate_predictions_perfect_and_imperfect():
    y_true = np.array([0, 0, 1, 1, 2, 2])
    y_pred_perf = np.array([0, 0, 1, 1, 2, 2])
    m_perf = evaluate_predictions(y_true, y_pred_perf)

    assert m_perf["accuracy"] == 1.0
    assert m_perf["balanced_accuracy"] == 1.0
    assert m_perf["macro_f1"] == 1.0
    assert m_perf["recall_desabasto"] == 1.0
    assert m_perf["recall_saturacion"] == 1.0

    y_pred_imp = np.array([0, 1, 0, 1, 2, 0])
    m_imp = evaluate_predictions(y_true, y_pred_imp)
    assert 0.0 < m_imp["balanced_accuracy"] < 1.0
    assert 0.0 < m_imp["macro_f1"] < 1.0


def test_mcnemar_test_identical_and_different():
    y_true = np.array([0, 1, 2, 0, 1, 2, 0, 1, 2, 0])
    y_pred_a = np.array([0, 1, 2, 0, 1, 2, 0, 1, 2, 0])
    y_pred_b = np.array([0, 1, 2, 0, 1, 2, 0, 1, 2, 0])

    res_same = mcnemar_test(y_true, y_pred_a, y_pred_b)
    assert res_same["discordant_pairs"] == 0
    assert res_same["p_value"] == 1.0
    assert not res_same["is_significant_at_05"]

    # Model B falla en varias donde A acierta
    y_pred_b_worse = np.array([1, 0, 0, 0, 1, 2, 0, 1, 2, 0])
    res_diff = mcnemar_test(y_true, y_pred_a, y_pred_b_worse)
    assert res_diff["discordant_pairs"] > 0
    assert "contingency_table" in res_diff


def test_bootstrap_metric_difference():
    rng = np.random.default_rng(123)
    y_true = rng.choice([0, 1, 2], size=200, p=[0.9, 0.05, 0.05])
    y_pred_a = y_true.copy()
    y_pred_b = y_true.copy()
    # Introducir errores controlados en B
    y_pred_b[rng.choice(200, size=20, replace=False)] = 0

    boot_res = bootstrap_metric_difference(y_true, y_pred_a, y_pred_b, n_bootstrap=50, seed=42)
    assert "macro_f1" in boot_res
    assert "recall_desabasto" in boot_res
    assert "ci_95_low" in boot_res["macro_f1"]
    assert "ci_95_high" in boot_res["macro_f1"]
