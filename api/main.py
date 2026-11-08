from typing import Literal

import pandas as pd
from fastapi import FastAPI
from pydantic import BaseModel, ConfigDict, Field

from api.model_loader import load_model


class PredictionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    capacity: float = Field(gt=0, allow_inf_nan=False)
    latitude: float = Field(ge=-90, le=90, allow_inf_nan=False)
    longitude: float = Field(ge=-180, le=180, allow_inf_nan=False)
    salidas_lag_1: float = Field(ge=0, allow_inf_nan=False)
    llegadas_lag_1: float = Field(ge=0, allow_inf_nan=False)
    salidas_lag_2: float = Field(ge=0, allow_inf_nan=False)
    llegadas_lag_2: float = Field(ge=0, allow_inf_nan=False)
    salidas_lag_24: float = Field(ge=0, allow_inf_nan=False)
    llegadas_lag_24: float = Field(ge=0, allow_inf_nan=False)
    salidas_lag_168: float = Field(ge=0, allow_inf_nan=False)
    llegadas_lag_168: float = Field(ge=0, allow_inf_nan=False)
    balance_rolling_3h: float = Field(allow_inf_nan=False)
    balance_rolling_12h: float = Field(allow_inf_nan=False)
    sin_hour: float = Field(ge=-1, le=1, allow_inf_nan=False)
    cos_hour: float = Field(ge=-1, le=1, allow_inf_nan=False)
    sin_dow: float = Field(ge=-1, le=1, allow_inf_nan=False)
    cos_dow: float = Field(ge=-1, le=1, allow_inf_nan=False)


class PredictionOutput(BaseModel):
    prediction: Literal[0, 1, 2]


app = FastAPI(
    title="MiBici Risk API"
)

model = load_model()


@app.get("/")
def health():
    return {
        "status": "ok",
        "model": "mibici-equipo30-p2-riesgo"
    }


@app.post("/predict")
def predict(features: PredictionInput) -> PredictionOutput:
    X = pd.DataFrame([features.model_dump()])

    prediction = model.predict(X)

    return PredictionOutput(prediction=int(prediction[0]))