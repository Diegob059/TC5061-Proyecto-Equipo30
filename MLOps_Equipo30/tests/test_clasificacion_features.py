import numpy as np
import pandas as pd
import pytest

from MiBici.clasificacion_features import (
    COLUMNAS_METADATOS,
    COLUMNAS_RESUMEN,
    FRANJAS_HORARIAS,
    construir_caracteristicas_estaciones,
    construir_perfil_horario,
    construir_perfil_por_franjas,
)


def _estaciones():
    return pd.DataFrame(
        {
            "estacion_id": [1, 2, 3],
            "name": ["A", "B", "C"],
            "latitude": [20.67, 20.68, 20.69],
            "longitude": [-103.36, -103.37, -103.38],
            "dpcapacity": [15, 15, 15],
        }
    )


def _viaje(origen, destino, hora, dia, minutos=10.0):
    """Un viaje que inicia a una hora dada en un día dado (alineado a días de la semana de Python)."""
    inicio = pd.Timestamp("2025-01-06") + pd.Timedelta(days=dia, hours=hora)  # 2025-01-06 es lunes
    return {
        "origen_id": origen,
        "destino_id": destino,
        "inicio": inicio,
        "fin": inicio + pd.Timedelta(minutes=minutos),
        "duracion_min": minutos,
    }


def test_construir_perfil_horario_filas_suman_uno():
    viajes = pd.DataFrame(
        [
            _viaje(1, 2, hora=8, dia=0),  # lunes (entre semana)
            _viaje(1, 2, hora=8, dia=0),
            _viaje(1, 2, hora=18, dia=0),
            _viaje(1, 2, hora=10, dia=5),  # sábado (fin de semana)
        ]
    )
    viajes["hora"] = viajes["inicio"].dt.hour
    viajes["fin_de_semana"] = viajes["inicio"].dt.dayofweek >= 5

    perfiles = construir_perfil_horario(viajes)
    assert perfiles.shape[1] == 48  # 24h x (lv, fds)
    np.testing.assert_allclose(perfiles.sum(axis=1).to_numpy(), 1.0)
    # La normalización es una distribución conjunta sobre los 48 bins (tipo_dia, hora),
    # es decir, cada celda es conteo / total_viajes_de_la_estacion (no por grupo de tipo_dia).
    assert perfiles.loc[1, "lv_08"] == pytest.approx(2 / 4)
    assert perfiles.loc[1, "fds_10"] == pytest.approx(1 / 4)


def test_construir_perfil_por_franjas_filas_suman_uno_y_agrupa_horas():
    viajes = pd.DataFrame(
        [
            _viaje(1, 2, hora=7, dia=0),  # pico_am
            _viaje(1, 2, hora=8, dia=0),  # pico_am
            _viaje(1, 2, hora=22, dia=0),  # noche
        ]
    )
    viajes["hora"] = viajes["inicio"].dt.hour
    viajes["fin_de_semana"] = viajes["inicio"].dt.dayofweek >= 5

    perfiles = construir_perfil_por_franjas(viajes)
    assert perfiles.shape[1] == 2 * len(FRANJAS_HORARIAS)
    np.testing.assert_allclose(perfiles.sum(axis=1).to_numpy(), 1.0)
    assert perfiles.loc[1, "lv_pico_am"] == pytest.approx(2 / 3)
    assert perfiles.loc[1, "lv_noche"] == pytest.approx(1 / 3)


def test_construir_caracteristicas_estaciones_filtra_bajo_volumen_y_excluye_ubicacion():
    # Las estaciones 1 y 2 cumplen el umbral salidas_minimas=2; la estación 3 (1 salida) se descarta.
    viajes = pd.DataFrame(
        [
            _viaje(1, 2, hora=8, dia=0),
            _viaje(1, 2, hora=8, dia=1),
            _viaje(1, 2, hora=9, dia=2),
            _viaje(2, 1, hora=18, dia=0),
            _viaje(2, 1, hora=19, dia=1),
            _viaje(3, 1, hora=9, dia=0),
        ]
    )

    caracteristicas, columnas_caracteristicas = construir_caracteristicas_estaciones(
        viajes, _estaciones(), granularidad="horario", salidas_minimas=2
    )

    assert set(caracteristicas.index) == {1, 2}  # estación 3 descartada: solo 1 salida
    assert set(COLUMNAS_METADATOS).issubset(caracteristicas.columns)
    assert "latitude" not in columnas_caracteristicas and "longitude" not in columnas_caracteristicas
    assert set(COLUMNAS_RESUMEN).issubset(columnas_caracteristicas)
    assert caracteristicas.loc[1, "salidas"] == 3
    assert caracteristicas.loc[2, "salidas"] == 2
    # La estación 2 envía 2 pero recibe los 3 viajes de la estación 1 -> balance neto positivo.
    assert caracteristicas.loc[2, "balance_rel"] > 0


def test_construir_caracteristicas_estaciones_rechaza_granularidad_desconocida():
    viajes = pd.DataFrame([_viaje(1, 2, hora=8, dia=0)])
    with pytest.raises(ValueError):
        construir_caracteristicas_estaciones(viajes, _estaciones(), granularidad="diario")
