"""Generador puro de payloads realistas de estaciones MiBici AMG para pruebas de carga.

Se mantiene desacoplado de `locust` (`gevent.monkey.patch_all()`) para permitir
validación unitaria directa dentro de PyTest sin alterar el runtime de hilos/sockets.
"""

from __future__ import annotations

import math
import random
from typing import Any

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
        hour = random.choice([7, 8, 9])
        salidas_1 = float(random.randint(6, 18))
        llegadas_1 = float(random.randint(0, 3))
        salidas_2 = float(random.randint(5, 15))
        llegadas_2 = float(random.randint(0, 4))
        balance_3h = round(random.uniform(-16.0, -4.0), 2)
        balance_12h = round(random.uniform(-22.0, -5.0), 2)
    elif profile == "saturacion_peak":
        hour = random.choice([17, 18, 19, 20])
        salidas_1 = float(random.randint(0, 3))
        llegadas_1 = float(random.randint(6, 18))
        salidas_2 = float(random.randint(0, 4))
        llegadas_2 = float(random.randint(5, 15))
        balance_3h = round(random.uniform(4.0, 16.0), 2)
        balance_12h = round(random.uniform(5.0, 22.0), 2)
    else:
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
