import numpy as np
import pandas as pd
import pytest

from MiBici.modeling.clasificacion_train import ajustar_y_evaluar, seleccionar_mejor


def _generar_grupos_sinteticos():
    """Dos grupos sintéticos bien separados, fáciles de recuperar para cualquier algoritmo de clustering."""
    rng = np.random.default_rng(42)
    grupo_a = rng.normal(loc=0.0, scale=0.2, size=(20, 3))
    grupo_b = rng.normal(loc=5.0, scale=0.2, size=(20, 3))
    return np.vstack([grupo_a, grupo_b])


@pytest.mark.parametrize("algoritmo", ["kmeans", "gmm"])
def test_ajustar_y_evaluar_recupera_dos_clusters_separados(algoritmo):
    X = _generar_grupos_sinteticos()
    modelo, etiquetas, metricas = ajustar_y_evaluar(X, algoritmo=algoritmo, k=2)

    assert len(etiquetas) == len(X)
    assert len(set(etiquetas)) == 2
    # Grupos bien separados deberían obtener un coeficiente de silueta cercano al máximo posible.
    assert metricas["silueta"] > 0.9
    assert metricas["tamanio_minimo_cluster"] == 20
    assert metricas["tamanio_maximo_cluster"] == 20
    if algoritmo == "kmeans":
        assert "inercia" in metricas
    else:
        assert "bic" in metricas and "aic" in metricas


def test_ajustar_y_evaluar_rechaza_algoritmo_desconocido():
    X = _generar_grupos_sinteticos()
    with pytest.raises(ValueError):
        ajustar_y_evaluar(X, algoritmo="dbscan", k=2)


def test_seleccionar_mejor_elige_mayor_silueta():
    resultados = pd.DataFrame(
        [
            {"conjunto_caracteristicas": "horario", "algoritmo": "kmeans", "k": 3, "silueta": 0.40},
            {"conjunto_caracteristicas": "horario", "algoritmo": "kmeans", "k": 4, "silueta": 0.55},
            {"conjunto_caracteristicas": "franjas", "algoritmo": "gmm", "k": 5, "silueta": 0.20},
        ]
    )
    mejor = seleccionar_mejor(resultados)
    assert mejor["k"] == 4
    assert mejor["algoritmo"] == "kmeans"
