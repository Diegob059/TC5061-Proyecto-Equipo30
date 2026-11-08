"""Pruebas del esquema de validación y el endpoint de predicción."""

import importlib

import pytest
from fastapi.testclient import TestClient


class StubModel:
    def __init__(self):
        self.called = False
        self.input_features = None

    def predict(self, features):
        self.called = True
        self.input_features = features
        return [2]


@pytest.fixture
def api_client(monkeypatch):
    loader = importlib.import_module("api.model_loader")
    model = StubModel()
    monkeypatch.setattr(loader, "load_model", lambda: model)

    api_module = importlib.import_module("api.main")
    api_module = importlib.reload(api_module)
    return TestClient(api_module.app), model


def valid_payload():
    return {
        "capacity": 20,
        "latitude": 20.67,
        "longitude": -103.35,
        "salidas_lag_1": 1,
        "llegadas_lag_1": 2,
        "salidas_lag_2": 1,
        "llegadas_lag_2": 2,
        "salidas_lag_24": 3,
        "llegadas_lag_24": 4,
        "salidas_lag_168": 5,
        "llegadas_lag_168": 6,
        "balance_rolling_3h": -1.5,
        "balance_rolling_12h": 0.5,
        "sin_hour": 0.5,
        "cos_hour": 0.866,
        "sin_dow": -0.5,
        "cos_dow": 0.866,
    }


def test_predict_accepts_model_features_and_returns_class(api_client):
    client, model = api_client

    response = client.post("/predict", json=valid_payload())

    assert response.status_code == 200
    assert response.json() == {"prediction": 2}
    assert model.called
    assert list(model.input_features.columns) == list(valid_payload())


@pytest.mark.parametrize(
    "update",
    [
        {"capacity": 0},
        {"sin_hour": 1.1},
        {"unexpected_feature": 1},
    ],
)
def test_predict_rejects_invalid_features(api_client, update):
    client, model = api_client
    payload = valid_payload()
    payload.update(update)

    response = client.post("/predict", json=payload)

    assert response.status_code == 422
    assert not model.called


def test_predict_rejects_missing_features(api_client):
    client, model = api_client
    payload = valid_payload()
    del payload["salidas_lag_168"]

    response = client.post("/predict", json=payload)

    assert response.status_code == 422
    assert not model.called
