"""Script para entrenar y registrar la Versión 2 (Challenger) en MLflow Model Registry.

Paso 4 de la Actividad:
1. Carga los datos de entrenamiento (2025) y prueba (2026).
2. Entrena un modelo LightGBM Challenger adaptado ante data drift con regularización L1/L2,
   submuestreo de características (colsample_bytree=0.8) y bagging (subsample=0.85).
3. Evalúa el desempeño y calcula métricas en Test 2026.
4. Registra el Run completo en el experimento `mibici-equipo30` en MLflow con firma,
   ejemplo de entrada y artefactos.
5. Registra el modelo en el Model Registry `mibici-equipo30-p2-riesgo` como Versión 2.
6. Asigna el alias `@challenger` a la Versión 2, preservando `@champion` en la Versión 1.
7. Guarda la evidencia auditable en `reports/p2/challenger_v2_registration.json`.
"""

import json
import os
import subprocess
import time
from pathlib import Path

import joblib
from lightgbm import LGBMClassifier
import mlflow
from mlflow.models.signature import infer_signature
from mlflow.tracking import MlflowClient
import numpy as np
import pandas as pd
from sklearn.metrics import (
    balanced_accuracy_score,
    classification_report,
    f1_score,
    precision_score,
    recall_score,
)

from src.data.p2_dataset import get_current_data_version
from src.features.p2_features import get_train_test_data
from src.p2_config import (
    FIGURES_DIR,
    MLFLOW_EXPERIMENT_NAME,
    MLFLOW_TRACKING_URI,
    P2_FEATURES_TARGET_PARQUET,
    P2_REGISTRY_NAME,
    P2_REPORTS_DIR,
    RANDOM_SEED,
    TARGET_HORIZON_HOURS,
    TRAIN_CUTOFF_DATE,
    TRAIN_END_DATE,
    logger,
)

CHALLENGER_CANDIDATE_ID = "lgbm_challenger_v2"
CHALLENGER_ALIAS = "challenger"

CHALLENGER_PARAMS = {
    "n_estimators": 160,
    "max_depth": 7,
    "num_leaves": 40,
    "learning_rate": 0.05,
    "min_child_samples": 40,
    "subsample": 0.85,
    "colsample_bytree": 0.80,
    "reg_alpha": 0.1,
    "reg_lambda": 0.5,
    "class_weight": "balanced",
    "random_state": RANDOM_SEED,
    "n_jobs": -1,
    "verbose": -1,
}


def _get_git_metadata() -> tuple[str, str]:
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL
        ).decode().strip()
        status = subprocess.check_output(
            ["git", "status", "--porcelain"], stderr=subprocess.DEVNULL
        ).decode().strip()
        return commit, "True" if status else "False"
    except Exception:
        return "unknown", "False"


def train_and_register_challenger(
    tracking_uri: str = MLFLOW_TRACKING_URI,
    model_name: str = P2_REGISTRY_NAME,
) -> dict:
    if not tracking_uri.startswith("http"):
        tracking_uri = os.getenv("MLFLOW_TRACKING_URI", "http://127.0.0.1:5001")

    logger.info("=" * 70)
    logger.info("ENTRENAMIENTO Y REGISTRO DE MODELO CHALLENGER V2 (PASO 4)")
    logger.info("=" * 70)
    logger.info(f"MLflow Tracking URI: {tracking_uri}")

    mlflow.set_tracking_uri(tracking_uri)
    client = MlflowClient(tracking_uri=tracking_uri)

    # 1. Cargar datos reproducibles
    logger.info("Cargando datos de entrenamiento (2025) y evaluación (2026)...")
    X_train, y_train, X_test, y_test, feature_cols, clean_df = get_train_test_data(
        features_parquet=P2_FEATURES_TARGET_PARQUET
    )
    data_version = get_current_data_version()
    git_commit, git_dirty = _get_git_metadata()

    logger.info(
        f"Datos cargados: Train={len(X_train)} filas, Test={len(X_test)} filas, "
        f"Variables={len(feature_cols)}"
    )

    # 2. Ajuste del modelo Challenger
    logger.info(f"Entrenando LGBMClassifier Challenger: '{CHALLENGER_CANDIDATE_ID}'...")
    clf = LGBMClassifier(**CHALLENGER_PARAMS)

    t0 = time.time()
    clf.fit(X_train, y_train)
    fit_duration = time.time() - t0
    logger.success(f"✓ Ajuste finalizado en {fit_duration:.2f} s")

    # Inferencia y métricas en Test 2026
    t_inf0 = time.time()
    y_pred = clf.predict(X_test)
    y_proba = clf.predict_proba(X_test)
    predict_duration = time.time() - t_inf0
    latency_ms_per_1k = (predict_duration / len(X_test)) * 1000 * 1000

    cand_metrics = {
        "macro_f1": float(f1_score(y_test, y_pred, average="macro", zero_division=0)),
        "balanced_accuracy": float(balanced_accuracy_score(y_test, y_pred)),
        "recall_normal": float(recall_score(y_test, y_pred, labels=[0], average="micro", zero_division=0)),
        "recall_desabasto": float(recall_score(y_test, y_pred, labels=[1], average="micro", zero_division=0)),
        "recall_saturacion": float(recall_score(y_test, y_pred, labels=[2], average="micro", zero_division=0)),
        "precision_normal": float(precision_score(y_test, y_pred, labels=[0], average="micro", zero_division=0)),
        "precision_desabasto": float(precision_score(y_test, y_pred, labels=[1], average="micro", zero_division=0)),
        "precision_saturacion": float(precision_score(y_test, y_pred, labels=[2], average="micro", zero_division=0)),
        "train_fit_duration_seconds": float(fit_duration),
        "test_predict_latency_ms_per_1k": float(latency_ms_per_1k),
    }

    logger.info(
        f"Métricas Challenger: Balanced Acc={cand_metrics['balanced_accuracy']:.4f} | "
        f"Macro F1={cand_metrics['macro_f1']:.4f} | "
        f"Recall Desabasto={cand_metrics['recall_desabasto']:.4f} | "
        f"Recall Saturación={cand_metrics['recall_saturacion']:.4f}"
    )

    # Serialización local del modelo
    models_dir = Path("models")
    models_dir.mkdir(parents=True, exist_ok=True)
    joblib_path = models_dir / "p2_lgbm_challenger_v2.joblib"
    joblib.dump(clf, joblib_path)
    logger.info(f"✓ Modelo serializado localmente en: {joblib_path}")

    # Guardar reporte de clasificación
    P2_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    rep_str = classification_report(
        y_test,
        y_pred,
        digits=4,
        target_names=["Normal (0)", "Desabasto (1)", "Saturación (2)"],
    )
    rep_path = P2_REPORTS_DIR / "p2_classification_report_lgbm_challenger_v2.txt"
    rep_path.write_text(rep_str, encoding="utf-8")

    cfg_path = P2_REPORTS_DIR / "p2_config_lgbm_challenger_v2.json"
    cfg_payload = {
        "candidate_id": CHALLENGER_CANDIDATE_ID,
        "description": "Modelo Challenger v2 adaptado ante drift con regularización L1/L2 y colsample=0.8",
        "params": CHALLENGER_PARAMS,
        "metrics": cand_metrics,
        "train_cutoff_date": TRAIN_CUTOFF_DATE,
        "train_end_date": TRAIN_END_DATE,
        "git_commit": git_commit,
        "data_version": data_version,
    }
    cfg_path.write_text(json.dumps(cfg_payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # 3. Loguear corrida en MLflow
    mlflow.set_experiment(MLFLOW_EXPERIMENT_NAME)
    run_name = f"p2_candidato_{CHALLENGER_CANDIDATE_ID}"

    with mlflow.start_run(run_name=run_name) as run:
        run_id = run.info.run_id
        logger.info(f"MLflow Run iniciado con ID: {run_id}")

        mlflow.log_params(CHALLENGER_PARAMS)
        mlflow.log_params({
            "candidate_id": CHALLENGER_CANDIDATE_ID,
            "model_class": "LGBMClassifier",
            "train_samples": len(X_train),
            "test_samples": len(X_test),
            "num_features": len(feature_cols),
            "train_end_date": TRAIN_END_DATE,
            "train_cutoff_date": TRAIN_CUTOFF_DATE,
            "data_version": data_version,
            "drift_adapted": "true",
        })

        mlflow.log_metrics(cand_metrics)

        mlflow.set_tags({
            "equipo": "Equipo 30",
            "pregunta": "P2",
            "question": "p2",
            "git_commit": git_commit,
            "git_dirty": git_dirty,
            "model_family": "LGBMClassifier",
            "stage_of_work": "candidate",
            "model_role": "challenger",
            "candidate_id": CHALLENGER_CANDIDATE_ID,
            "author": "Ricardo Bahamon (Equipo 30)",
            "target_horizon": "2_hours",
            "problem_type": "multiclass_imbalanced",
            "drift_adapted": "true",
        })

        input_example = X_test.head(5)
        signature = infer_signature(input_example, y_pred[:5])
        mlflow.sklearn.log_model(
            clf,
            artifact_path="model",
            signature=signature,
            input_example=input_example,
        )

        mlflow.log_artifact(str(rep_path), artifact_path="reports")
        mlflow.log_artifact(str(cfg_path), artifact_path="config")

    # 4. Registrar en el Model Registry como nueva versión
    uri = f"runs:/{run_id}/model"
    logger.info(f"Registrando en Model Registry: '{model_name}' desde {uri}...")
    version_obj = mlflow.register_model(uri, model_name)
    version_num = str(version_obj.version)
    logger.success(f"✓ Modelo registrado como '{model_name}' Versión {version_num}")

    reason_desc = (
        f"Versión {version_num} (Challenger): Modelo LightGBM adaptado ante data drift con regularización "
        f"L1/L2 (alpha=0.1, lambda=0.5), submuestreo de variables (colsample=0.8) y bagging (subsample=0.85) "
        f"para mitigar la deriva observada en balances rodantes (Wasserstein > 0.06). "
        f"Balanced Acc={cand_metrics['balanced_accuracy']:.4f}, Macro F1={cand_metrics['macro_f1']:.4f}."
    )

    client.update_model_version(model_name, version_num, description=reason_desc)

    # Etiquetas en la versión
    client.set_model_version_tag(model_name, version_num, "candidate_id", CHALLENGER_CANDIDATE_ID)
    client.set_model_version_tag(model_name, version_num, "source_run_id", run_id)
    client.set_model_version_tag(model_name, version_num, "git_commit", git_commit)
    client.set_model_version_tag(model_name, version_num, "data_version", data_version)
    client.set_model_version_tag(model_name, version_num, "drift_adapted", "true")
    client.set_model_version_tag(model_name, version_num, "selection_reason", reason_desc)

    # Asignar alias `@challenger`
    logger.info(f"Asignando alias '{CHALLENGER_ALIAS}' a la versión {version_num}...")
    client.set_registered_model_alias(model_name, CHALLENGER_ALIAS, version_num)
    logger.success(f"✓ Alias '{CHALLENGER_ALIAS}' asignado a la versión {version_num}.")

    # Verificar que versión 1 mantiene alias champion
    rm = client.get_registered_model(model_name)
    logger.info(f"Aliases actuales de '{model_name}': {rm.aliases}")
    assert "champion" in rm.aliases, "El alias 'champion' no debe perderse."
    assert rm.aliases[CHALLENGER_ALIAS] == version_num, f"Alias {CHALLENGER_ALIAS} debe apuntar a {version_num}."

    # Prueba de inferencia desde URI alias
    challenger_uri = f"models:/{model_name}@{CHALLENGER_ALIAS}"
    logger.info(f"Probando inferencia desde alias: {challenger_uri}...")
    restored = mlflow.pyfunc.load_model(challenger_uri)
    test_preds = np.asarray(restored.predict(input_example)).ravel()
    np.testing.assert_array_equal(y_pred[:5], test_preds)
    logger.success(f"✓ Inferencia verificada exitosamente desde {challenger_uri}.")

    evidence = {
        "model_name": model_name,
        "version": version_num,
        "alias": CHALLENGER_ALIAS,
        "model_uri": challenger_uri,
        "run_id": run_id,
        "candidate_id": CHALLENGER_CANDIDATE_ID,
        "metrics": cand_metrics,
        "params": CHALLENGER_PARAMS,
        "description": reason_desc,
        "registered_aliases": rm.aliases,
        "verified_inference": True,
    }

    out_evidence_path = P2_REPORTS_DIR / "challenger_v2_registration.json"
    out_evidence_path.write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    logger.success(f"✓ Evidencia guardada en: {out_evidence_path}")

    return evidence


if __name__ == "__main__":
    train_and_register_challenger()
