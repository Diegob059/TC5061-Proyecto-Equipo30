"""Funciones de graficación para el pipeline de clustering de estaciones de MiBici.

Se usan tanto de forma independiente como desde `MiBici/modeling/clasificacion_train.py`,
que registra las figuras que regresan como artefactos de MLflow para el
modelo ganador.
"""

from pathlib import Path

from loguru import logger
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
import typer

from MiBici.config import FIGURES_DIR, PROCESSED_DATA_DIR

aplicacion = typer.Typer()


def graficar_seleccion_k(resultados: pd.DataFrame) -> plt.Figure:
    """Coeficiente de silueta vs. k, una línea por combinación (conjunto_caracteristicas, algoritmo).

    `resultados` es la tabla del barrido producida por
    `MiBici.modeling.clasificacion_train.ejecutar_barrido`, con al menos las
    columnas conjunto_caracteristicas, algoritmo, k, silueta.
    """
    fig, ax = plt.subplots(figsize=(9, 5))
    for (conjunto_caracteristicas, algoritmo), grupo in resultados.groupby(["conjunto_caracteristicas", "algoritmo"]):
        grupo = grupo.sort_values("k")
        ax.plot(grupo["k"], grupo["silueta"], marker="o", label=f"{conjunto_caracteristicas} / {algoritmo}")
    ax.set_xlabel("k (número de clusters)")
    ax.set_ylabel("Coeficiente de silueta")
    ax.set_title("Selección de k por conjunto de features y algoritmo")
    ax.legend()
    fig.tight_layout()
    return fig


def graficar_mapa_calor_perfil_clusters(
    df: pd.DataFrame, columnas_caracteristicas: list[str], etiquetas: np.ndarray
) -> plt.Figure:
    """Promedio de cada feature (sin escalar) por cluster, como mapa de calor.

    Esto es lo que hace interpretables los clusters: cada fila es un
    cluster, cada columna una feature, y el color muestra cómo se compara
    ese cluster con los demás en esa feature.
    """
    perfil = df[columnas_caracteristicas].groupby(etiquetas).mean()
    perfil.index.name = "cluster"
    fig, ax = plt.subplots(figsize=(max(8, len(columnas_caracteristicas) * 0.35), max(3, perfil.shape[0] * 0.6)))
    sns.heatmap(perfil, cmap="vlag", center=0 if (perfil.min().min() < 0) else None, annot=False, ax=ax)
    ax.set_title("Perfil promedio de cada cluster (features sin escalar)")
    fig.tight_layout()
    return fig


def graficar_mapa_clusters(df: pd.DataFrame, etiquetas: np.ndarray) -> plt.Figure:
    """Dispersa las estaciones en el mapa, coloreadas por cluster, para interpretar dónde está cada patrón."""
    fig, ax = plt.subplots(figsize=(8, 8))
    paleta = sns.color_palette("tab10", n_colors=len(set(etiquetas)))
    for id_cluster in sorted(set(etiquetas)):
        mascara = etiquetas == id_cluster
        ax.scatter(
            df.loc[mascara, "longitude"],
            df.loc[mascara, "latitude"],
            s=30,
            alpha=0.85,
            color=paleta[id_cluster % len(paleta)],
            label=f"Cluster {id_cluster}",
        )
    ax.set_xlabel("Longitud")
    ax.set_ylabel("Latitud")
    ax.set_aspect(1 / np.cos(np.deg2rad(20.67)))
    ax.set_title("Estaciones coloreadas por cluster de patrón de uso")
    ax.legend(loc="upper left", bbox_to_anchor=(1, 1))
    fig.tight_layout()
    return fig


@aplicacion.command()
def main(
    ruta_entrada: Path = PROCESSED_DATA_DIR / "estaciones_clusters.parquet",
    ruta_salida: Path = FIGURES_DIR / "mapa_clusters.png",
):
    """CLI independiente: grafica las asignaciones de cluster guardadas en el mapa."""
    df = pd.read_parquet(ruta_entrada)
    fig = graficar_mapa_clusters(df, df["cluster"].to_numpy())
    ruta_salida.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(ruta_salida, dpi=150)
    logger.success(f"Guardado: {ruta_salida}")


if __name__ == "__main__":
    aplicacion()
