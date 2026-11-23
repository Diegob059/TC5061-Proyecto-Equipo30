"""Escenario de pruebas de carga con Locust para la API de Riesgo Operativo MiBici.

Simula peticiones concurrentes provenientes del Centro de Control Operativo (CCO)
y los procesos de telemetría de las 470 estaciones del Área Metropolitana de
Guadalajara (AMG), combinando perfiles de operación normal, riesgo de desabasto
en pico matutino y riesgo de saturación en pico vespertino.

Uso interactivo (UI web en http://localhost:8089):
    locust -f load_tests/locustfile.py --host http://127.0.0.1:8000

Uso automatizado (headless con exportación CSV y HTML):
    locust -f load_tests/locustfile.py --host http://127.0.0.1:8000 \
        --headless -u 50 -r 10 -t 45s \
        --csv reports/semana10/locust_50u --html reports/semana10/locust_50u.html
"""

from __future__ import annotations

import math
import random
from typing import Any

from locust import HttpUser, between, task

# Rango geográfico real del polígono de estaciones MiBici en Guadalajara (AMG)
AMG_LAT_RANGE = (20.640, 20.720)
AMG_LON_RANGE = (-103.400, -103.320)
STATION_CAPACITIES = (11, 15, 19, 20, 23, 27, 31, 35)


def build_station_payload(profile: str | None = None) -> dict[str, Any]:
    """Construye un payload válido de 17 features acorde al contrato Pydantic de la API."""
    if profile is None:
        profile = random.choices(
            population=["desabasto_peak", "saturacion_peak", "normal_valley"],
            weights=[0.35, 0.35, 0.30],
            k=1,
        )[0]

    capacity = random.choice(STATION_CAPACITIES)
    latitude = round(random.uniform(*AMG_LAT_RANGE), 5)
    longitude = round(random.uniform(*AMG_LON_RANGE), 5)
    dow = random.randint(0, 6)

    if profile == "desabasto_peak":
        # Hora pico matutina (7-9 AM): salidas muy superiores a llegadas
        hour = random.choice([7, 8, 9])
        salidas_1 = float(random.randint(6, 18))
        llegadas_1 = float(random.randint(0, 3))
        salidas_2 = float(random.randint(5, 15))
        llegadas_2 = float(random.randint(0, 4))
        balance_3h = round(random.uniform(-16.0, -4.0), 2)
        balance_12h = round(random.uniform(-22.0, -5.0), 2)
    elif profile == "saturacion_peak":
        # Hora pico vespertina (17-20 PM): llegadas acumuladas saturando anclajes
        hour = random.choice([17, 18, 19, 20])
        salidas_1 = float(random.randint(0, 3))
        llegadas_1 = float(random.randint(6, 18))
        salidas_2 = float(random.randint(0, 4))
        llegadas_2 = float(random.randint(5, 15))
        balance_3h = round(random.uniform(4.0, 16.0), 2)
        balance_12h = round(random.uniform(5.0, 22.0), 2)
    else:
        # Operación estable / horas valle
        hour = random.choice([11, 12, 13, 14, 15, 21])
        salidas_1 = float(random.randint(0, 5))
        llegadas_1 = float(random.randint(0, 5))
        salidas_2 = float(random.randint(0, 5))
        llegadas_2 = float(random.randint(0, 5))
        balance_3h = round(random.uniform(-2.5, 2.5), 2)
        balance_12h = round(random.uniform(-4.0, 4.0), 2)

    angle_hour = 2.0 * math.pi * hour / 24.0
    angle_dow = 2.0 * math.pi * dow / 7.0

    return {
        "capacity": capacity,
        "latitude": latitude,
        "longitude": longitude,
        "salidas_lag_1": salidas_1,
        "llegadas_lag_1": llegadas_1,
        "salidas_lag_2": salidas_2,
        "llegadas_lag_2": llegadas_2,
        "salidas_lag_24": float(max(0, int(salidas_1 + random.randint(-2, 2)))),
        "llegadas_lag_24": float(max(0, int(llegadas_1 + random.randint(-2, 2)))),
        "salidas_lag_168": float(max(0, int(salidas_1 + random.randint(-3, 3)))),
        "llegadas_lag_168": float(max(0, int(llegadas_1 + random.randint(-3, 3)))),
        "balance_rolling_3h": balance_3h,
        "balance_rolling_12h": balance_12h,
        "sin_hour": round(math.sin(angle_hour), 4),
        "cos_hour": round(math.cos(angle_hour), 4),
        "sin_dow": round(math.sin(angle_dow), 4),
        "cos_dow": round(math.cos(angle_dow), 4),
    }


class MiBiciDispatcherUser(HttpUser):
    """Usuario virtual que representa consultas operativas al microservicio MiBici."""

    # Pausa breve entre peticiones para modelar polling continuo realista en alta concurrencia
    wait_time = between(0.1, 0.5)

    @task(10)
    def predict_station_risk(self) -> None:
        """Envía una solicitud de inferencia de riesgo operativo a 2 horas."""
        payload = build_station_payload()
        with self.client.post(
            "/predict",
            json=payload,
            name="POST /predict",
            catch_response=True,
        ) as response:
            if response.status_code != 200:
                response.failure(f"HTTP {response.status_code}: {response.text[:120]}")
                return
            try:
                body = response.json()
            except ValueError as exc:
                response.failure(f"JSON inválido: {exc}")
                return
            prediction = body.get("prediction")
            if type(prediction) is not int or prediction not in (0, 1, 2):
                response.failure(f"Predicción fuera de contrato: {body}")
            else:
                response.success()

    @task(1)
    def check_health(self) -> None:
        """Consulta el endpoint de salud utilizado por orquestadores y balanceadores."""
        with self.client.get("/health", name="GET /health", catch_response=True) as response:
            if response.status_code == 200 and response.json().get("status") == "healthy":
                response.success()
            else:
                response.failure(f"Health inválido: HTTP {response.status_code}")

    @task(1)
    def check_model_info(self) -> None:
        """Verifica los metadatos y linaje del modelo activo."""
        with self.client.get(
            "/model-info", name="GET /model-info", catch_response=True
        ) as response:
            if response.status_code == 200 and "model_uri" in response.json():
                response.success()
            else:
                response.failure(f"Model info inválido: HTTP {response.status_code}")
