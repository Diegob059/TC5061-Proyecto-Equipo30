from pathlib import Path

from loguru import logger
from tqdm import tqdm
import typer

from MiBici.config import MODELS_DIR, PROCESSED_DATA_DIR

aplicacion = typer.Typer()


@aplicacion.command()
def main(
    # ---- REEMPLAZAR LAS RUTAS POR DEFECTO SEGÚN CORRESPONDA ----
    ruta_caracteristicas: Path = PROCESSED_DATA_DIR / "test_features.csv",
    ruta_modelo: Path = MODELS_DIR / "model.pkl",
    ruta_predicciones: Path = PROCESSED_DATA_DIR / "test_predictions.csv",
    # -----------------------------------------
):
    # ---- REEMPLAZAR ESTO CON TU PROPIO CÓDIGO ----
    logger.info("Realizando inferencia del modelo...")
    for i in tqdm(range(10), total=10):
        if i == 5:
            logger.info("Algo ocurrió en la iteración 5.")
    logger.success("Inferencia completa.")
    # -----------------------------------------


if __name__ == "__main__":
    aplicacion()
