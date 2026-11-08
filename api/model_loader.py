"""Módulo de carga desacoplada del modelo Champion desde el Model Registry de MLflow."""

import os
from typing import Any

import mlflow

try:
    from dotenv import load_dotenv

    # Carga variables locales (.env) si existen; en contenedores se leen de variables de entorno
    load_dotenv()
except ImportError:
    pass

MODEL_URI = os.getenv("MODEL_URI", "models:/mibici-equipo30-p2-riesgo@champion")


def get_tracking_uri() -> str:
    """Retorna la URI configurada de MLflow Tracking."""
    return os.getenv("MLFLOW_TRACKING_URI", "http://host.containers.internal:5000")


def load_model():
    """Carga el modelo Champion serializado desde el Model Registry de MLflow."""
    tracking_uri = get_tracking_uri()
    mlflow.set_tracking_uri(tracking_uri)
    return mlflow.pyfunc.load_model(MODEL_URI)


def get_model_metadata() -> dict[str, Any]:
    """Retorna metadatos descriptivos de la configuración y procedencia del modelo."""
    return {
        "model_uri": MODEL_URI,
        "model_name": "mibici-equipo30-p2-riesgo",
        "alias": "champion",
        "tracking_uri": get_tracking_uri(),
        "task": "Multiclass Station Risk Classification (0: Normal, 1: Desabasto, 2: Saturacion)",
        "prediction_horizon": "2 horas",
    }
