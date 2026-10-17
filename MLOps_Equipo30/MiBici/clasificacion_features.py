"""Ingeniería de features para el pipeline de clustering de estaciones de MiBici.

Lee las tablas de viajes/estaciones limpias escritas por ``MiBici/clasificacion_dataset.py``
en ``data/interim/`` y construye una tabla de features por estación para el
clustering (``MiBici/modeling/clasificacion_train.py``). Se generan dos conjuntos de
features para que el propio conjunto pueda compararse como una dimensión más
del experimento en MLflow:

- "horario": perfil completo de 24h x (entre semana / fin de semana) de
  proporción de salidas.
- "franjas": el mismo perfil colapsado en un puñado de franjas horarias
  interpretables.

Ambos conjuntos de features comparten las mismas estadísticas resumen no
temporales (volumen, balance, rotación, duración) y ambos excluyen
deliberadamente latitud/longitud: la ubicación solo se conserva como
metadato para mapear/interpretar los clusters después (ver
``MiBici/clasificacion_plots.py``), no se usa para formarlos.
"""

from pathlib import Path
from typing import Dict, List, Tuple

from loguru import logger
import numpy as np
import pandas as pd
import typer

from MiBici.config import INTERIM_DATA_DIR, PROCESSED_DATA_DIR

aplicacion = typer.Typer()

# Hora -> franja horaria usada por el conjunto de features "franjas".
FRANJAS_HORARIAS: Dict[str, Tuple[int, ...]] = {
    "madrugada": (0, 1, 2, 3, 4, 5),
    "pico_am": (6, 7, 8, 9),
    "medio_dia": (10, 11, 12, 13, 14, 15),
    "pico_pm": (16, 17, 18, 19),
    "noche": (20, 21, 22, 23),
}

# Mismo umbral de actividad usado en el notebook de EDA para que las
# proporciones horarias sean estables.
SALIDAS_MINIMAS = 500

# Columnas que describen/dan contexto a una estación pero no son insumos de clustering.
COLUMNAS_METADATOS: List[str] = [
    "name",
    "latitude",
    "longitude",
    "dpcapacity",
    "salidas",
    "llegadas",
    "total",
]

COLUMNAS_RESUMEN: List[str] = [
    "log_total",
    "balance_rel",
    "rotacion_por_anclaje",
    "duracion_mediana",
]


def cargar_viajes_limpios(dir_intermedios: Path = INTERIM_DATA_DIR) -> pd.DataFrame:
    """Carga la tabla de viajes limpia escrita por `MiBici/clasificacion_dataset.py`."""
    ruta = dir_intermedios / "viajes_limpios.parquet"
    viajes = pd.read_parquet(ruta)
    logger.info(f"Viajes cargados desde {ruta}: {len(viajes):,}")
    return viajes


def cargar_estaciones_limpias(dir_intermedios: Path = INTERIM_DATA_DIR) -> pd.DataFrame:
    """Carga el catálogo de estaciones ya restringido a las estaciones comunes a todos los meses."""
    ruta = dir_intermedios / "estaciones.parquet"
    estaciones = pd.read_parquet(ruta)
    logger.info(f"Estaciones cargadas desde {ruta}: {len(estaciones)}")
    return estaciones


def agregar_campos_tiempo(viajes: pd.DataFrame) -> pd.DataFrame:
    """Agrega las columnas de hora del día / bandera de fin de semana con las que se construyen los perfiles."""
    df = viajes.copy()
    df["hora"] = df["inicio"].dt.hour
    df["fin_de_semana"] = df["inicio"].dt.dayofweek >= 5
    return df


def construir_perfil_horario(viajes: pd.DataFrame) -> pd.DataFrame:
    """Proporción de salidas de cada estación por hora, separado entre semana (lv) / fin de semana (fds).

    Cada fila suma 1 (ignorando estaciones con cero salidas, lo cual no puede
    ocurrir aquí ya que quien llama a esta función solo pasa estaciones
    "activas" ya filtradas).
    """
    tipo_dia = np.where(viajes["fin_de_semana"], "fds", "lv")
    perfiles = (
        viajes.assign(tipo_dia=tipo_dia)
        .groupby(["origen_id", "tipo_dia", "hora"])
        .size()
        .unstack(["tipo_dia", "hora"], fill_value=0)
        .reindex(columns=pd.MultiIndex.from_product([["lv", "fds"], range(24)]), fill_value=0)
    )
    perfiles = perfiles.div(perfiles.sum(axis=1), axis=0)
    perfiles.columns = [f"{t}_{h:02d}" for t, h in perfiles.columns]
    return perfiles


def construir_perfil_por_franjas(viajes: pd.DataFrame) -> pd.DataFrame:
    """Proporción de salidas de cada estación por franja horaria, separado lv / fds."""
    hora_a_franja = {h: franja for franja, horas in FRANJAS_HORARIAS.items() for h in horas}
    tipo_dia = np.where(viajes["fin_de_semana"], "fds", "lv")
    franja = viajes["hora"].map(hora_a_franja)
    perfiles = (
        viajes.assign(tipo_dia=tipo_dia, franja=franja)
        .groupby(["origen_id", "tipo_dia", "franja"])
        .size()
        .unstack(["tipo_dia", "franja"], fill_value=0)
        .reindex(columns=pd.MultiIndex.from_product([["lv", "fds"], FRANJAS_HORARIAS.keys()]), fill_value=0)
    )
    perfiles = perfiles.div(perfiles.sum(axis=1), axis=0)
    perfiles.columns = [f"{t}_{b}" for t, b in perfiles.columns]
    return perfiles


def construir_caracteristicas_estaciones(
    viajes: pd.DataFrame,
    estaciones: pd.DataFrame,
    granularidad: str = "horario",
    salidas_minimas: int = SALIDAS_MINIMAS,
) -> Tuple[pd.DataFrame, List[str]]:
    """Construye la tabla de features por estación usada para el clustering.

    Parámetros
    ----------
    granularidad: "horario" para el perfil completo de 24h o "franjas" para
        las franjas horarias reducidas. Ambas comparten las mismas features resumen.
    salidas_minimas: estaciones con menos salidas que este umbral se
        descartan, ya que sus proporciones horarias serían demasiado
        ruidosas para formar un perfil estable.

    Regresa
    -------
    Una tupla (df_caracteristicas, columnas_caracteristicas): `df_caracteristicas`
    está indexado por `estacion_id` y contiene tanto las columnas de metadatos
    (`COLUMNAS_METADATOS`, para contexto/mapeo) como las columnas de features
    de clustering; `columnas_caracteristicas` lista exactamente estas
    últimas, es decir, las columnas que deben escalarse y alimentarse al
    modelo de clustering en `MiBici/modeling/clasificacion_train.py`.
    """
    if granularidad not in {"horario", "franjas"}:
        raise ValueError(f"granularidad debe ser 'horario' o 'franjas', recibido: {granularidad!r}")

    viajes = agregar_campos_tiempo(viajes)

    salidas = viajes.groupby("origen_id").size().rename("salidas")
    llegadas = viajes.groupby("destino_id").size().rename("llegadas")
    duracion_mediana = viajes.groupby("origen_id")["duracion_min"].median().rename("duracion_mediana")

    df = (
        estaciones.set_index("estacion_id")[["name", "latitude", "longitude", "dpcapacity"]]
        .join(salidas)
        .join(llegadas)
        .join(duracion_mediana)
        .fillna({"salidas": 0, "llegadas": 0})
    )
    df["total"] = df["salidas"] + df["llegadas"]
    df["log_total"] = np.log1p(df["total"])
    df["balance_rel"] = (df["llegadas"] - df["salidas"]) / df["total"].replace(0, np.nan)
    df["rotacion_por_anclaje"] = df["salidas"] / df["dpcapacity"].replace(0, np.nan)
    df["duracion_mediana"] = df["duracion_mediana"].fillna(df["duracion_mediana"].median())
    df[["balance_rel", "rotacion_por_anclaje"]] = df[["balance_rel", "rotacion_por_anclaje"]].fillna(0)

    activas = df.index[df["salidas"] >= salidas_minimas]
    logger.info(f"Estaciones con >= {salidas_minimas} salidas: {len(activas)} (descartadas: {len(df) - len(activas)})")

    viajes_activos = viajes[viajes["origen_id"].isin(activas)]
    perfiles = (
        construir_perfil_horario(viajes_activos)
        if granularidad == "horario"
        else construir_perfil_por_franjas(viajes_activos)
    )

    resultado = df.loc[activas].join(perfiles)
    columnas_caracteristicas = COLUMNAS_RESUMEN + list(perfiles.columns)
    logger.success(f"Features ({granularidad}): {resultado.shape[0]} estaciones x {len(columnas_caracteristicas)} features")
    return resultado, columnas_caracteristicas


@aplicacion.command()
def main(
    dir_intermedios: Path = INTERIM_DATA_DIR,
    dir_salida: Path = PROCESSED_DATA_DIR,
    salidas_minimas: int = SALIDAS_MINIMAS,
):
    """Construye y escribe ambos conjuntos de features ("horario" y "franjas") en `data/processed/`."""
    viajes = cargar_viajes_limpios(dir_intermedios)
    estaciones = cargar_estaciones_limpias(dir_intermedios)
    dir_salida.mkdir(parents=True, exist_ok=True)

    for granularidad in ("horario", "franjas"):
        caracteristicas, columnas_caracteristicas = construir_caracteristicas_estaciones(
            viajes, estaciones, granularidad=granularidad, salidas_minimas=salidas_minimas
        )
        ruta_salida = dir_salida / f"estaciones_caracteristicas_{granularidad}.parquet"
        caracteristicas.to_parquet(ruta_salida)
        logger.success(
            f"Guardado: {ruta_salida} ({caracteristicas.shape[0]} estaciones x "
            f"{len(columnas_caracteristicas)} features de clustering)"
        )


if __name__ == "__main__":
    aplicacion()
