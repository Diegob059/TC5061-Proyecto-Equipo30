"""API REST para inferencia en tiempo real de riesgo operativo en estaciones MiBici.

Empaqueta el modelo LightGBM multiclase (Pregunta 2) recuperado desde el Model Registry de MLflow.
"""

from typing import Any, Literal

import pandas as pd
from fastapi import FastAPI
from pydantic import BaseModel, ConfigDict, Field

from api.model_loader import get_model_metadata, load_model


class PredictionInput(BaseModel):
    """Esquema de validación estricto de las características de entrada para inferencia."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "capacity": 20.0,
                    "latitude": 20.67,
                    "longitude": -103.35,
                    "salidas_lag_1": 1.0,
                    "llegadas_lag_1": 2.0,
                    "salidas_lag_2": 1.0,
                    "llegadas_lag_2": 2.0,
                    "salidas_lag_24": 3.0,
                    "llegadas_lag_24": 4.0,
                    "salidas_lag_168": 5.0,
                    "llegadas_lag_168": 6.0,
                    "balance_rolling_3h": -1.5,
                    "balance_rolling_12h": 0.5,
                    "sin_hour": 0.5,
                    "cos_hour": 0.866,
                    "sin_dow": -0.5,
                    "cos_dow": 0.866,
                }
            ]
        },
    )

    capacity: float = Field(
        gt=0,
        allow_inf_nan=False,
        description="Capacidad total de anclajes físicos instalados en la estación",
    )
    latitude: float = Field(
        ge=-90,
        le=90,
        allow_inf_nan=False,
        description="Latitud geográfica de la estación (WGS84)",
    )
    longitude: float = Field(
        ge=-180,
        le=180,
        allow_inf_nan=False,
        description="Longitud geográfica de la estación (WGS84)",
    )
    salidas_lag_1: float = Field(
        ge=0,
        allow_inf_nan=False,
        description="Viajes iniciados (salidas) en la estación hace 1 hora (t-1)",
    )
    llegadas_lag_1: float = Field(
        ge=0,
        allow_inf_nan=False,
        description="Viajes finalizados (llegadas) en la estación hace 1 hora (t-1)",
    )
    salidas_lag_2: float = Field(
        ge=0,
        allow_inf_nan=False,
        description="Viajes iniciados en la estación hace 2 horas (t-2)",
    )
    llegadas_lag_2: float = Field(
        ge=0,
        allow_inf_nan=False,
        description="Viajes finalizados en la estación hace 2 horas (t-2)",
    )
    salidas_lag_24: float = Field(
        ge=0,
        allow_inf_nan=False,
        description="Viajes iniciados a la misma hora del día anterior (t-24)",
    )
    llegadas_lag_24: float = Field(
        ge=0,
        allow_inf_nan=False,
        description="Viajes finalizados a la misma hora del día anterior (t-24)",
    )
    salidas_lag_168: float = Field(
        ge=0,
        allow_inf_nan=False,
        description="Viajes iniciados a la misma hora y día de la semana anterior (t-168)",
    )
    llegadas_lag_168: float = Field(
        ge=0,
        allow_inf_nan=False,
        description="Viajes finalizados a la misma hora y día de la semana anterior (t-168)",
    )
    balance_rolling_3h: float = Field(
        allow_inf_nan=False,
        description="Balance neto móvil de los últimos 3 periodos horarios (llegadas - salidas)",
    )
    balance_rolling_12h: float = Field(
        allow_inf_nan=False,
        description="Balance neto móvil de las últimas 12 horas",
    )
    sin_hour: float = Field(
        ge=-1,
        le=1,
        allow_inf_nan=False,
        description="Componente seno de la codificación cíclica de la hora (0-23)",
    )
    cos_hour: float = Field(
        ge=-1,
        le=1,
        allow_inf_nan=False,
        description="Componente coseno de la codificación cíclica de la hora (0-23)",
    )
    sin_dow: float = Field(
        ge=-1,
        le=1,
        allow_inf_nan=False,
        description="Componente seno de la codificación cíclica del día de la semana (0-6)",
    )
    cos_dow: float = Field(
        ge=-1,
        le=1,
        allow_inf_nan=False,
        description="Componente coseno de la codificación cíclica del día de la semana (0-6)",
    )


class PredictionOutput(BaseModel):
    """Esquema de salida de la predicción de riesgo operativo."""

    prediction: Literal[0, 1, 2] = Field(
        description="Clase predicha: 0 = Normal, 1 = Desabasto (riesgo de vaciarse a 2h), 2 = Saturacion (riesgo de llenarse a 2h)"
    )


app = FastAPI(
    title="MiBici Risk Prediction API",
    description=(
        "API REST de inferencia en tiempo real para anticipación de riesgos operativos "
        "(Desabasto y Saturación) en estaciones del sistema MiBici Guadalajara en un horizonte "
        "de 2 horas. MLOps Equipo 30."
    ),
    version="1.0.0",
)

model = load_model()


@app.get("/", tags=["Health & Status"])
def root() -> dict[str, str]:
    """Endpoint raíz con verificación básica de salud y nombre del modelo."""
    return {
        "status": "ok",
        "model": "mibici-equipo30-p2-riesgo",
    }


@app.get("/health", tags=["Health & Status"])
def health() -> dict[str, str]:
    """Health check operativo del servicio."""
    return {
        "status": "healthy",
        "service": "MiBici Risk API",
        "version": "1.0.0",
    }


@app.get("/model-info", tags=["Model Metadata"])
def model_info() -> dict[str, Any]:
    """Retorna información detallada de procedencia y linaje del modelo cargado."""
    return get_model_metadata()


@app.post("/predict", response_model=PredictionOutput, tags=["Inference"])
def predict(features: PredictionInput) -> PredictionOutput:
    """Ejecuta inferencia en tiempo real sobre las características de la estación.

    Alinea los tipos del DataFrame a los tipos estrictos del schema del modelo en MLflow
    (capacity como int32 y variables continuas como float32) para prevenir fallas de validación.
    """
    data = features.model_dump()
    X = pd.DataFrame([data])

    for col in X.columns:
        if col == "capacity":
            X[col] = X[col].astype("int32")
        else:
            X[col] = X[col].astype("float32")

    prediction = model.predict(X)

    return PredictionOutput(prediction=int(prediction[0]))
