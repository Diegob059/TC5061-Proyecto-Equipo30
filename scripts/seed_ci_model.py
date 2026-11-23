"""Registra un modelo LightGBM liviano o copia el Champion en un servidor MLflow destino.

Uso en CI/CD (validación de Docker Compose sin depender de los 21 CSVs de producción):
    python scripts/seed_ci_model.py --tracking-uri http://127.0.0.1:5001

Uso para replicar el Champion real desde otro servidor MLflow (por ejemplo, host -> Compose):
    python scripts/seed_ci_model.py --tracking-uri http://127.0.0.1:5002 \
        --source-tracking-uri http://127.0.0.1:5001
"""

from __future__ import annotations

import argparse
import os
import tempfile
from pathlib import Path

import lightgbm as lgb
import mlflow
import mlflow.lightgbm
import numpy as np
import pandas as pd
from mlflow.models.signature import infer_signature
from mlflow.tracking import MlflowClient

MODEL_NAME = "mibici-equipo30-p2-riesgo"
ALIAS = "champion"
FEATURE_COLUMNS = [
    "capacity",
    "latitude",
    "longitude",
    "salidas_lag_1",
    "llegadas_lag_1",
    "salidas_lag_2",
    "llegadas_lag_2",
    "salidas_lag_24",
    "llegadas_lag_24",
    "salidas_lag_168",
    "llegadas_lag_168",
    "balance_rolling_3h",
    "balance_rolling_12h",
    "sin_hour",
    "cos_hour",
    "sin_dow",
    "cos_dow",
]


def build_synthetic_dataset(n_samples: int = 300, seed: int = 42) -> tuple[pd.DataFrame, np.ndarray]:
    """Genera una muestra sintética alineada al esquema estricto de P2 (17 variables)."""
    rng = np.random.default_rng(seed)
    df = pd.DataFrame(
        {
            "capacity": rng.integers(11, 36, size=n_samples).astype("int32"),
            "latitude": rng.uniform(20.64, 20.72, size=n_samples).astype("float32"),
            "longitude": rng.uniform(-103.40, -103.32, size=n_samples).astype("float32"),
            "salidas_lag_1": rng.poisson(4.0, size=n_samples).astype("float32"),
            "llegadas_lag_1": rng.poisson(4.0, size=n_samples).astype("float32"),
            "salidas_lag_2": rng.poisson(3.5, size=n_samples).astype("float32"),
            "llegadas_lag_2": rng.poisson(3.5, size=n_samples).astype("float32"),
            "salidas_lag_24": rng.poisson(4.0, size=n_samples).astype("float32"),
            "llegadas_lag_24": rng.poisson(4.0, size=n_samples).astype("float32"),
            "salidas_lag_168": rng.poisson(4.0, size=n_samples).astype("float32"),
            "llegadas_lag_168": rng.poisson(4.0, size=n_samples).astype("float32"),
            "balance_rolling_3h": rng.normal(0.0, 3.0, size=n_samples).astype("float32"),
            "balance_rolling_12h": rng.normal(0.0, 5.0, size=n_samples).astype("float32"),
            "sin_hour": rng.uniform(-1.0, 1.0, size=n_samples).astype("float32"),
            "cos_hour": rng.uniform(-1.0, 1.0, size=n_samples).astype("float32"),
            "sin_dow": rng.uniform(-1.0, 1.0, size=n_samples).astype("float32"),
            "cos_dow": rng.uniform(-1.0, 1.0, size=n_samples).astype("float32"),
        }
    )[FEATURE_COLUMNS]

    y = np.zeros(n_samples, dtype=np.int32)
    y[df["balance_rolling_3h"] < -2.0] = 1  # Riesgo de Desabasto
    y[df["balance_rolling_3h"] > 2.0] = 2   # Riesgo de Saturación
    return df, y


def seed_model(
    tracking_uri: str,
    source_tracking_uri: str | None = None,
    model_name: str = MODEL_NAME,
    alias: str = ALIAS,
) -> str:
    """Registra el modelo en MLflow destino y asigna el alias champion."""
    X_sample, y_sample = build_synthetic_dataset()

    if source_tracking_uri:
        mlflow.set_tracking_uri(source_tracking_uri)
        source_uri = f"models:/{model_name}@{alias}"
        with tempfile.TemporaryDirectory() as tmpdir:
            local_dir = mlflow.artifacts.download_artifacts(artifact_uri=source_uri, dst_path=tmpdir)
            loaded = mlflow.lightgbm.load_model(local_dir)
        model = loaded
        origin_tag = f"replicated_from:{source_tracking_uri}"
    else:
        model = lgb.LGBMClassifier(
            objective="multiclass",
            num_class=3,
            n_estimators=25,
            max_depth=5,
            num_leaves=15,
            random_state=42,
            n_jobs=1,
            verbose=-1,
        )
        model.fit(X_sample, y_sample)
        origin_tag = "ci_smoke_synthetic"

    mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_experiment("mibici-equipo30-ci")
    signature = infer_signature(X_sample.head(5), model.predict(X_sample.head(5)))

    with mlflow.start_run(run_name=f"seed_{origin_tag}") as run:
        mlflow.set_tag("origin", origin_tag)
        mlflow.set_tag("question", "p2")
        model_info = mlflow.lightgbm.log_model(
            lgb_model=model,
            name="model",
            signature=signature,
            input_example=X_sample.head(2),
        )
        mv = mlflow.register_model(model_uri=model_info.model_uri, name=model_name)

    client = MlflowClient(tracking_uri=tracking_uri)
    client.set_registered_model_alias(model_name, alias, mv.version)
    print(f"OK: registrado {model_name}@{alias} -> versión {mv.version} ({origin_tag}) en {tracking_uri}")
    return str(mv.version)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--tracking-uri",
        default=os.getenv("MLFLOW_TRACKING_URI", "http://127.0.0.1:5001"),
        help="URI del servidor MLflow destino",
    )
    parser.add_argument(
        "--source-tracking-uri",
        default=None,
        help="URI opcional de un servidor MLflow origen del cual replicar el modelo @champion",
    )
    args = parser.parse_args()
    seed_model(tracking_uri=args.tracking_uri, source_tracking_uri=args.source_tracking_uri)


if __name__ == "__main__":
    main()
