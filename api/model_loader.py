import os
import mlflow

MODEL_URI = "models:/mibici-equipo30-p2-riesgo@champion"


def load_model():
    tracking_uri = os.getenv(
        "MLFLOW_TRACKING_URI",
        "http://host.containers.internal:5000"
    )

    mlflow.set_tracking_uri(tracking_uri)

    return mlflow.pyfunc.load_model(MODEL_URI)