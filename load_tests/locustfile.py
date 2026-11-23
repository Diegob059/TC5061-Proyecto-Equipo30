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

from locust import HttpUser, between, task

from load_tests.payloads import build_station_payload


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
