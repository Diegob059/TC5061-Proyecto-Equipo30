"""Pipeline de preprocesamiento para los datos de viajes de MiBici.

Carga los CSV crudos de viajes mensuales y el catálogo de estaciones desde
``data/raw/`` (ver ``src/data/download_raw_data.py``), aplica los filtros de
calidad de datos decididos durante el EDA
(``notebooks/1.0-pregunta-e-riesgo-estaciones.ipynb``), y escribe una tabla
de viajes limpia junto con un catálogo de estaciones correspondiente en
``data/interim/`` listos para la ingeniería de features
(``MiBici/clasificacion_features.py``).
"""

from pathlib import Path
from typing import Iterable, Optional

from loguru import logger
import pandas as pd
import typer

from MiBici.config import INTERIM_DATA_DIR, RAW_DATA_DIR

aplicacion = typer.Typer()

SUBDIR_VIAJES = "Viajes"
SUBDIR_ESTACIONES = "Nomenclatura"

# La codificación del encabezado "Año_de_nacimiento" es inconsistente entre
# archivos mensuales (UTF-8 vs. Latin-1 con caracteres mal interpretados), por
# lo que las columnas se renombran por posición en lugar de depender de los
# nombres del encabezado.
COLUMNAS_VIAJES = [
    "viaje_id",
    "usuario_id",
    "genero",
    "anio_nacimiento",
    "inicio",
    "fin",
    "origen_id",
    "destino_id",
]

DURACION_MINIMA_DEFECTO = 1.0
DURACION_MAXIMA_DEFECTO = 180.0


def _leer_archivo_viajes(ruta: Path) -> pd.DataFrame:
    """Lee un único CSV mensual de viajes de MiBici con la codificación/columnas correctas."""
    df = pd.read_csv(
        ruta,
        encoding="latin-1",
        header=0,
        names=COLUMNAS_VIAJES,
        dtype={
            "viaje_id": "int64",
            "usuario_id": "int64",
            "genero": "string",
            "origen_id": "int32",
            "destino_id": "int32",
        },
    )
    df["archivo"] = ruta.stem[-7:]  # p. ej. "2025_01"
    return df


def cargar_viajes(dir_crudos: Path = RAW_DATA_DIR, patron: str = "datos_abiertos_202[0-9]_*.csv") -> pd.DataFrame:
    """Carga y concatena todos los archivos mensuales de viajes encontrados en ``dir_crudos/Viajes``."""
    dir_viajes = dir_crudos / SUBDIR_VIAJES
    archivos = sorted(dir_viajes.glob(patron))
    if not archivos:
        raise FileNotFoundError(f"No se encontraron archivos de viajes en {dir_viajes}")
    logger.info(f"Cargando {len(archivos)} archivos de viajes desde {dir_viajes}")
    viajes = pd.concat([_leer_archivo_viajes(f) for f in archivos], ignore_index=True)
    viajes["inicio"] = pd.to_datetime(viajes["inicio"], errors="coerce")
    viajes["fin"] = pd.to_datetime(viajes["fin"], errors="coerce")
    logger.info(f"Viajes cargados: {len(viajes):,}")
    return viajes


def cargar_estaciones(dir_crudos: Path = RAW_DATA_DIR, patron: str = "nomenclatura_*.csv") -> pd.DataFrame:
    """Carga el catálogo de estaciones más reciente encontrado en ``dir_crudos/Nomenclatura``."""
    dir_estaciones = dir_crudos / SUBDIR_ESTACIONES
    archivos = sorted(dir_estaciones.glob(patron))
    if not archivos:
        raise FileNotFoundError(f"No se encontró catálogo de estaciones en {dir_estaciones}")
    estaciones = pd.read_csv(archivos[-1], encoding="latin-1").rename(columns={"id": "estacion_id"})
    logger.info(f"Catálogo de estaciones: {archivos[-1].name} ({len(estaciones)} estaciones)")
    return estaciones


def obtener_estaciones_comunes(viajes: pd.DataFrame) -> set:
    """Regresa los ids de estación presentes (como origen o destino) en todos los meses de ``viajes``.

    Las estaciones abiertas después del primer mes (p. ej. nuevas estaciones
    agregadas durante 2025/2026) están ausentes en los archivos más antiguos y
    por lo tanto quedan excluidas por esta intersección, que es exactamente
    el criterio solicitado para evitar contar estaciones recién abiertas.
    """
    comunes: Optional[set] = None
    for _, df_mes in viajes.groupby("archivo"):
        ids = set(df_mes["origen_id"]) | set(df_mes["destino_id"])
        comunes = ids if comunes is None else (comunes & ids)
    comunes = comunes or set()
    logger.info(f"Estaciones presentes en los {viajes['archivo'].nunique()} meses: {len(comunes)}")
    return comunes


def limpiar_viajes(
    viajes: pd.DataFrame,
    estaciones_comunes: Optional[Iterable[int]] = None,
    duracion_minima_min: float = DURACION_MINIMA_DEFECTO,
    duracion_maxima_min: float = DURACION_MAXIMA_DEFECTO,
) -> pd.DataFrame:
    """Aplica los filtros de calidad de datos decididos para el pipeline de clustering.

    Filtros (ver ``notebooks/1.0-pregunta-e-riesgo-estaciones.ipynb`` para el
    EDA que motiva cada uno):

    - Elimina filas exactamente duplicadas.
    - Elimina filas con ``genero`` o ``anio_nacimiento`` faltante.
    - Conserva solo viajes con duración en ``[duracion_minima_min, duracion_maxima_min]``.
    - Si se da ``estaciones_comunes``, conserva solo viajes donde tanto el
      origen como el destino estén en ese conjunto (estaciones activas
      durante todo el periodo, es decir, excluyendo las recién abiertas).
    """
    df = viajes.copy()
    n0 = len(df)

    columnas_dedup = [c for c in df.columns if c != "archivo"]
    df = df.drop_duplicates(subset=columnas_dedup)
    logger.info(f"Tras eliminar duplicados: {len(df):,} ({n0 - len(df):,} descartados)")

    n1 = len(df)
    df = df.dropna(subset=["genero", "anio_nacimiento"])
    logger.info(f"Tras eliminar genero/anio_nacimiento nulos: {len(df):,} ({n1 - len(df):,} descartados)")

    n2 = len(df)
    duracion_min = (df["fin"] - df["inicio"]).dt.total_seconds() / 60
    mascara_duracion = duracion_min.between(duracion_minima_min, duracion_maxima_min)
    df = df.loc[mascara_duracion].copy()
    df["duracion_min"] = duracion_min.loc[mascara_duracion]
    logger.info(
        f"Tras filtrar duración [{duracion_minima_min}, {duracion_maxima_min}] min: "
        f"{len(df):,} ({n2 - len(df):,} descartados)"
    )

    if estaciones_comunes is not None:
        n3 = len(df)
        estaciones_comunes = set(estaciones_comunes)
        df = df[df["origen_id"].isin(estaciones_comunes) & df["destino_id"].isin(estaciones_comunes)]
        logger.info(f"Tras filtrar estaciones comunes a todos los meses: {len(df):,} ({n3 - len(df):,} descartados)")

    logger.success(f"Limpieza completa: {len(df):,}/{n0:,} viajes conservados ({len(df) / n0 * 100:.1f}%)")
    return df.reset_index(drop=True)


@aplicacion.command()
def main(
    dir_crudos: Path = RAW_DATA_DIR,
    ruta_salida_viajes: Path = INTERIM_DATA_DIR / "viajes_limpios.parquet",
    ruta_salida_estaciones: Path = INTERIM_DATA_DIR / "estaciones.parquet",
    duracion_minima_min: float = DURACION_MINIMA_DEFECTO,
    duracion_maxima_min: float = DURACION_MAXIMA_DEFECTO,
):
    """Carga viajes + estaciones crudos, los limpia, y escribe el resultado en ``data/interim/``."""
    viajes = cargar_viajes(dir_crudos)
    estaciones = cargar_estaciones(dir_crudos)

    estaciones_comunes = obtener_estaciones_comunes(viajes) & set(estaciones["estacion_id"])
    viajes_limpios = limpiar_viajes(
        viajes,
        estaciones_comunes=estaciones_comunes,
        duracion_minima_min=duracion_minima_min,
        duracion_maxima_min=duracion_maxima_min,
    )
    estaciones_limpias = estaciones[estaciones["estacion_id"].isin(estaciones_comunes)].reset_index(drop=True)

    ruta_salida_viajes.parent.mkdir(parents=True, exist_ok=True)
    ruta_salida_estaciones.parent.mkdir(parents=True, exist_ok=True)
    viajes_limpios.to_parquet(ruta_salida_viajes, index=False)
    estaciones_limpias.to_parquet(ruta_salida_estaciones, index=False)
    logger.success(f"Guardado: {ruta_salida_viajes} ({len(viajes_limpios):,} filas)")
    logger.success(f"Guardado: {ruta_salida_estaciones} ({len(estaciones_limpias):,} estaciones)")


if __name__ == "__main__":
    aplicacion()
