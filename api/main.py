from fastapi import FastAPI
from typing import Dict
import pandas as pd

from api.model_loader import load_model

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
def predict(features: Dict):

    X = pd.DataFrame([features])

    prediction = model.predict(X)

    return {
        "prediction": int(prediction[0])
    }