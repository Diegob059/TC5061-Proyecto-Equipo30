"""Genera un reporte Evidently para drift y calidad de datos de P2."""

import json
import platform
import time
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from typing import Annotated

import typer

from src.config import REPORTS_DIR
from src.p2_config import (
    P2_FEATURES_TARGET_PARQUET,
    TRAIN_CUTOFF_DATE,
    TRAIN_END_DATE,
)
from src.validation.evidently_report import generate_evidently_report
from src.validation.p2_checks import file_sha256, load_dataset_samples

app = typer.Typer(help="Reporte Evidently de calidad y drift temporal para P2.")


@app.command()
def main(
    sample_size: Annotated[
        int, typer.Option(min=2, help="Número total de filas muestreadas.")
    ] = 15000,
    data_path: Annotated[
        Path | None, typer.Option(help="Parquet procesado de características P2.")
    ] = None,
    output_dir: Annotated[
        Path, typer.Option(help="Directorio para los reportes HTML y JSON.")
    ] = REPORTS_DIR / "evidently",
):
    """Compara Train 2025 como referencia con Test 2026 como datos actuales."""
    started = time.monotonic()
    parquet_path = data_path or P2_FEATURES_TARGET_PARQUET
    try:
        reference, current, features = load_dataset_samples(
            parquet_path, sample_size=sample_size
        )
    except (FileNotFoundError, ValueError) as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=2) from error

    output_html = output_dir / "p2_data_drift.html"
    output_json = output_dir / "p2_data_drift.json"
    generate_evidently_report(
        reference,
        current,
        features,
        output_html=output_html,
        output_json=output_json,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    summary = {
        "generated_at": datetime.now(UTC).isoformat(),
        "dataset": parquet_path.name,
        "dataset_sha256": file_sha256(parquet_path),
        "reference_period": {
            "rule": f"timestamp < {TRAIN_CUTOFF_DATE}",
            "purpose": "Distribución de referencia usada para entrenar el modelo P2.",
            "rows_sampled": len(reference),
        },
        "current_period": {
            "rule": f"timestamp >= {TRAIN_END_DATE}",
            "purpose": (
                "Periodo posterior disponible para representar los datos actuales "
                "de producción."
            ),
            "rows_sampled": len(current),
        },
        "sampling": {"method": "random reproducible after temporal split", "seed": 42},
        "feature_count": len(features),
        "feature_columns": features,
        "preparation": "src.features.p2_features.get_train_test_data",
        "reports": {
            "html": output_html.name,
            "json": output_json.name,
        },
        "versions": {
            "evidently": version("evidently"),
            "pandas": version("pandas"),
        },
        "python_version": platform.python_version(),
        "elapsed_seconds": round(time.monotonic() - started, 2),
    }
    summary_path = output_dir / "p2_data_drift_summary.json"
    summary_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    typer.echo(
        f"Reporte generado: {output_html}\n"
        f"Resumen: {summary_path}\n"
        f"Referencia: {len(reference)} filas | Actual: {len(current)} filas | "
        f"Variables: {len(features)}"
    )


if __name__ == "__main__":
    app()
