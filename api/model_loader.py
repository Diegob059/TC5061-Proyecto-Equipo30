"""Módulo de carga desacoplada del modelo Champion desde el Model Registry de MLflow."""

import os
import re
from datetime import UTC, datetime
from typing import Any

import mlflow
import mlflow.pyfunc

try:
    from dotenv import load_dotenv

    # Carga variables locales (.env) si existen; en contenedores se leen de variables de entorno
    load_dotenv()
except ImportError:
    pass

MODEL_URI = os.getenv("MODEL_URI", "models:/mibici-equipo30-p2-riesgo@champion")
_loaded_metadata: dict[str, Any] = {}


def get_tracking_uri() -> str:
    """Retorna la URI configurada de MLflow Tracking."""
    return os.getenv("MLFLOW_TRACKING_URI", "http://host.containers.internal:5000")


def load_model():
    """Resuelve el alias una vez y carga esa versión inmutable del Registry."""
    tracking_uri = get_tracking_uri()
    mlflow.set_tracking_uri(tracking_uri)
    resolved_uri = MODEL_URI
    metadata: dict[str, Any] = {}
    match = re.fullmatch(r"models:/([^/@]+)(?:@([^/]+)|/(\d+))", MODEL_URI)
    if match:
        name, alias, version = match.groups()
        client = mlflow.tracking.MlflowClient(tracking_uri=tracking_uri)
        mv = (client.get_model_version_by_alias(name, alias) if alias
              else client.get_model_version(name, version))
        resolved_uri = f"models:/{name}/{mv.version}"
        metadata.update(model_name=name, alias=alias, model_version=str(mv.version), run_id=mv.run_id)
        if mv.run_id:
            run = client.get_run(mv.run_id)
            metadata["origin"] = run.data.tags.get("origin")
    model = mlflow.pyfunc.load_model(resolved_uri)
    model_info = getattr(model, "metadata", None)
    metadata.update(
        resolved_model_uri=resolved_uri,
        run_id=getattr(model_info, "run_id", None) or metadata.get("run_id"),
        model_uuid=getattr(model_info, "model_uuid", None),
        loaded_at_utc=datetime.now(UTC).isoformat(),
    )
    metadata["provenance_status"] = (
        "identified" if metadata.get("model_version") and metadata.get("run_id") else "unresolved"
    )
    _loaded_metadata.clear()
    _loaded_metadata.update(metadata)
    return model


def get_model_metadata() -> dict[str, Any]:
    """Retorna metadatos descriptivos de la configuración y procedencia del modelo."""
    return {
        "model_uri": MODEL_URI,
        "model_name": "mibici-equipo30-p2-riesgo",
        "alias": "champion",
        "tracking_uri": get_tracking_uri(),
        "task": "Multiclass Station Risk Classification (0: Normal, 1: Desabasto, 2: Saturacion)",
        "prediction_horizon": "2 horas",
        **_loaded_metadata,
    }
