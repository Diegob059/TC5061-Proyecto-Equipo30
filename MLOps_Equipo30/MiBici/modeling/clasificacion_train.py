"""Definición del modelo, entrenamiento y selección de modelo con seguimiento
en MLflow para el pipeline de clustering de estaciones de MiBici.

Lee ambos conjuntos de features escritos por `MiBici/clasificacion_features.py` desde
`data/processed/`, escala cada uno de forma independiente, y recorre modelos
K-Means y Gaussian Mixture para k = 2..10 en cada conjunto de features. Cada
combinación (conjunto_caracteristicas, algoritmo, k) se registra como su
propia corrida de MLflow (anidada bajo una corrida padre "model_selection")
con sus hiperparámetros, métricas de calidad de cluster, y el modelo
ajustado como artefacto. La combinación con el mayor coeficiente de silueta
se vuelve a guardar en `models/cluster_model.pkl` para
`MiBici/modeling/clasificacion_predict.py`, y las asignaciones de cluster/figuras
resultantes se registran en la corrida padre y se guardan en
`reports/figures/` y `data/processed/`.
"""

from dataclasses import dataclass
from pathlib import Path

from loguru import logger
import joblib
import mlflow
import mlflow.sklearn
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import davies_bouldin_score, silhouette_score
from sklearn.mixture import GaussianMixture
from sklearn.preprocessing import StandardScaler
import typer

from MiBici.config import (
    FIGURES_DIR,
    MLFLOW_TRACKING_URI,
    MODELS_DIR,
    PROCESSED_DATA_DIR,
)
from MiBici.clasificacion_features import COLUMNAS_METADATOS
from MiBici.clasificacion_plots import graficar_mapa_calor_perfil_clusters, graficar_mapa_clusters, graficar_seleccion_k

aplicacion = typer.Typer()

CONJUNTOS_CARACTERISTICAS = ("horario", "franjas")
ALGORITMOS = ("kmeans", "gmm")
K_MINIMO, K_MAXIMO = 2, 10
ESTADO_ALEATORIO = 42
# Nombre propio del experimento de MLflow para este modelo de clustering. No se
# importa de `MiBici.config` porque `MLFLOW_EXPERIMENT_NAME` ahí es específico
# del modelo de riesgo de otra pregunta (config.py es infraestructura
# compartida, pero el nombre del experimento es propio de cada modelo).
NOMBRE_EXPERIMENTO_MLFLOW = "mibici-clustering"


@dataclass
class ResultadoBarrido:
    """Todo lo necesario para volver a guardar, predecir o graficar la
    combinación ganadora sin tener que reajustarla."""

    modelo: object
    escalador: StandardScaler
    conjunto_caracteristicas: str
    algoritmo: str
    k: int
    columnas_caracteristicas: list[str]
    etiquetas: np.ndarray


def cargar_conjunto_caracteristicas(
    nombre: str, dir_procesados: Path = PROCESSED_DATA_DIR
) -> tuple[pd.DataFrame, list[str]]:
    """Carga una tabla de features por estación escrita por `MiBici/clasificacion_features.py` y separa metadatos/features."""
    ruta = dir_procesados / f"estaciones_caracteristicas_{nombre}.parquet"
    df = pd.read_parquet(ruta)
    columnas_caracteristicas = [c for c in df.columns if c not in COLUMNAS_METADATOS]
    logger.info(
        f"Conjunto de features '{nombre}': {df.shape[0]} estaciones x "
        f"{len(columnas_caracteristicas)} features ({ruta.name})"
    )
    return df, columnas_caracteristicas


def ajustar_y_evaluar(X: np.ndarray, algoritmo: str, k: int, estado_aleatorio: int = ESTADO_ALEATORIO):
    """Ajusta un modelo de clustering y calcula sus métricas de calidad de cluster.

    Regresa (modelo, etiquetas, metricas). `metricas` siempre tiene
    "silueta", "davies_bouldin", "tamanio_minimo_cluster" y
    "tamanio_maximo_cluster", más "inercia" para k-means o "bic"/"aic" para gmm.
    """
    if algoritmo == "kmeans":
        modelo = KMeans(n_clusters=k, random_state=estado_aleatorio, n_init=10)
        etiquetas = modelo.fit_predict(X)
        metricas = {"inercia": float(modelo.inertia_)}
    elif algoritmo == "gmm":
        modelo = GaussianMixture(n_components=k, random_state=estado_aleatorio)
        etiquetas = modelo.fit_predict(X)
        metricas = {"bic": float(modelo.bic(X)), "aic": float(modelo.aic(X))}
    else:
        raise ValueError(f"algoritmo debe ser 'kmeans' o 'gmm', recibido: {algoritmo!r}")

    metricas["silueta"] = float(silhouette_score(X, etiquetas))
    metricas["davies_bouldin"] = float(davies_bouldin_score(X, etiquetas))
    tamanios = pd.Series(etiquetas).value_counts()
    metricas["tamanio_minimo_cluster"] = int(tamanios.min())
    metricas["tamanio_maximo_cluster"] = int(tamanios.max())
    return modelo, etiquetas, metricas


def seleccionar_mejor(resultados: pd.DataFrame) -> pd.Series:
    """Elige la corrida con el mayor coeficiente de silueta."""
    return resultados.sort_values("silueta", ascending=False).iloc[0]


def ejecutar_barrido(
    conjuntos_caracteristicas: tuple = CONJUNTOS_CARACTERISTICAS,
    algoritmos: tuple = ALGORITMOS,
    rango_k: range = range(K_MINIMO, K_MAXIMO + 1),
    dir_procesados: Path = PROCESSED_DATA_DIR,
) -> tuple[pd.DataFrame, dict[tuple[str, str, int], ResultadoBarrido]]:
    """Ejecuta el barrido completo (conjunto_caracteristicas x algoritmo x k), registrando cada combinación en MLflow.

    Regresa la tabla de resultados (una fila por corrida) y un diccionario de
    resultados ajustados indexado por (conjunto_caracteristicas, algoritmo, k),
    para poder inspeccionar/guardar/graficar la combinación ganadora sin
    volver a ajustarla.
    """
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    mlflow.set_experiment(NOMBRE_EXPERIMENTO_MLFLOW)

    filas = []
    ajustados: dict[tuple[str, str, int], ResultadoBarrido] = {}

    with mlflow.start_run(run_name="model_selection"):
        mlflow.log_params(
            {
                "conjuntos_caracteristicas": ",".join(conjuntos_caracteristicas),
                "algoritmos": ",".join(algoritmos),
                "k_minimo": rango_k.start,
                "k_maximo": rango_k.stop - 1,
            }
        )

        for conjunto_caracteristicas in conjuntos_caracteristicas:
            df, columnas_caracteristicas = cargar_conjunto_caracteristicas(conjunto_caracteristicas, dir_procesados)
            escalador = StandardScaler()
            X = escalador.fit_transform(df[columnas_caracteristicas])

            for algoritmo in algoritmos:
                for k in rango_k:
                    with mlflow.start_run(run_name=f"{conjunto_caracteristicas}_{algoritmo}_k{k}", nested=True):
                        modelo, etiquetas, metricas = ajustar_y_evaluar(X, algoritmo, k)

                        mlflow.log_params(
                            {
                                "conjunto_caracteristicas": conjunto_caracteristicas,
                                "algoritmo": algoritmo,
                                "k": k,
                                "n_estaciones": X.shape[0],
                                "n_caracteristicas": X.shape[1],
                            }
                        )
                        mlflow.log_metrics(metricas)
                        mlflow.sklearn.log_model(modelo, name="modelo")

                        filas.append(
                            {
                                "conjunto_caracteristicas": conjunto_caracteristicas,
                                "algoritmo": algoritmo,
                                "k": k,
                                **metricas,
                            }
                        )
                        ajustados[(conjunto_caracteristicas, algoritmo, k)] = ResultadoBarrido(
                            modelo=modelo,
                            escalador=escalador,
                            conjunto_caracteristicas=conjunto_caracteristicas,
                            algoritmo=algoritmo,
                            k=k,
                            columnas_caracteristicas=columnas_caracteristicas,
                            etiquetas=etiquetas,
                        )

        resultados = pd.DataFrame(filas)
        mejor = seleccionar_mejor(resultados)
        clave_mejor = (mejor["conjunto_caracteristicas"], mejor["algoritmo"], int(mejor["k"]))
        logger.success(
            f"Mejor combinación: {mejor['conjunto_caracteristicas']} / {mejor['algoritmo']} / k={int(mejor['k'])} "
            f"(silueta={mejor['silueta']:.3f})"
        )

        # --- Artefactos registrados una sola vez en la corrida padre: comparación del barrido + perfil/mapa del modelo ganador ---
        FIGURES_DIR.mkdir(parents=True, exist_ok=True)

        figura_seleccion_k = graficar_seleccion_k(resultados)
        mlflow.log_figure(figura_seleccion_k, "comparacion_silueta.png")
        figura_seleccion_k.savefig(FIGURES_DIR / "2.0_seleccion_k.png", dpi=150)

        ruta_resultados = dir_procesados / "resultados_sweep.csv"
        resultados.to_csv(ruta_resultados, index=False)
        mlflow.log_artifact(str(ruta_resultados))

        mejor_resultado = ajustados[clave_mejor]
        df_mejor, _ = cargar_conjunto_caracteristicas(mejor_resultado.conjunto_caracteristicas, dir_procesados)

        figura_perfil = graficar_mapa_calor_perfil_clusters(
            df_mejor, mejor_resultado.columnas_caracteristicas, mejor_resultado.etiquetas
        )
        mlflow.log_figure(figura_perfil, "perfil_clusters.png")
        figura_perfil.savefig(FIGURES_DIR / "2.0_perfil_clusters.png", dpi=150)

        figura_mapa = graficar_mapa_clusters(df_mejor, mejor_resultado.etiquetas)
        mlflow.log_figure(figura_mapa, "mapa_clusters.png")
        figura_mapa.savefig(FIGURES_DIR / "2.0_mapa_clusters.png", dpi=150)

        mlflow.log_params(
            {
                "mejor_conjunto_caracteristicas": mejor["conjunto_caracteristicas"],
                "mejor_algoritmo": mejor["algoritmo"],
                "mejor_k": int(mejor["k"]),
            }
        )
        mlflow.log_metric("mejor_silueta", mejor["silueta"])

    return resultados, ajustados


def guardar_mejor_modelo(
    resultados: pd.DataFrame,
    ajustados: dict[tuple[str, str, int], ResultadoBarrido],
    dir_modelos: Path = MODELS_DIR,
) -> Path:
    """Persiste la combinación ganadora (conjunto_caracteristicas, algoritmo, k) en `models/` para `clasificacion_predict.py`."""
    mejor = seleccionar_mejor(resultados)
    clave = (mejor["conjunto_caracteristicas"], mejor["algoritmo"], int(mejor["k"]))
    resultado = ajustados[clave]

    dir_modelos.mkdir(parents=True, exist_ok=True)
    ruta_salida = dir_modelos / "cluster_model.pkl"
    joblib.dump(
        {
            "modelo": resultado.modelo,
            "escalador": resultado.escalador,
            "conjunto_caracteristicas": resultado.conjunto_caracteristicas,
            "algoritmo": resultado.algoritmo,
            "k": resultado.k,
            "columnas_caracteristicas": resultado.columnas_caracteristicas,
        },
        ruta_salida,
    )
    logger.success(f"Modelo guardado: {ruta_salida}")
    return ruta_salida


def guardar_asignaciones_cluster(
    ajustados: dict[tuple[str, str, int], ResultadoBarrido],
    resultados: pd.DataFrame,
    dir_procesados: Path = PROCESSED_DATA_DIR,
) -> Path:
    """Escribe las asignaciones de cluster por estación del modelo ganador en `data/processed/`.

    Esta es la tabla que responde la pregunta de negocio original: qué
    estaciones comparten un patrón de uso (la columna `cluster`) y dónde
    están (las columnas de metadatos `latitude`/`longitude` ya presentes en
    la tabla).
    """
    mejor = seleccionar_mejor(resultados)
    clave = (mejor["conjunto_caracteristicas"], mejor["algoritmo"], int(mejor["k"]))
    resultado = ajustados[clave]

    df, _ = cargar_conjunto_caracteristicas(resultado.conjunto_caracteristicas, dir_procesados)
    df["cluster"] = resultado.etiquetas

    ruta_salida = dir_procesados / "estaciones_clusters.parquet"
    df.to_parquet(ruta_salida)
    logger.success(f"Asignaciones de cluster guardadas: {ruta_salida}")
    return ruta_salida


@aplicacion.command()
def main(dir_procesados: Path = PROCESSED_DATA_DIR, dir_modelos: Path = MODELS_DIR):
    """Ejecuta el barrido completo de selección de modelo con seguimiento en MLflow y persiste el modelo ganador."""
    resultados, ajustados = ejecutar_barrido(dir_procesados=dir_procesados)
    guardar_mejor_modelo(resultados, ajustados, dir_modelos=dir_modelos)
    guardar_asignaciones_cluster(ajustados, resultados, dir_procesados=dir_procesados)


if __name__ == "__main__":
    aplicacion()
