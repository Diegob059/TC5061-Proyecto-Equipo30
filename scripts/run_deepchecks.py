"""Genera informes de DeepChecks y devuelve 1 si hay condiciones incumplidas o errores."""

import json
import platform
import time
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from typing import Annotated

import pandas as pd
import typer

from src.config import REPORTS_DIR
from src.p2_config import P2_FEATURES_TARGET_PARQUET, TRAIN_CUTOFF_DATE, TRAIN_END_DATE
from src.validation.p2_checks import (
    file_sha256,
    load_dataset_samples,
    run_data_integrity_suite,
    run_train_test_drift_suite,
)

app = typer.Typer(
    help="Auditoría de datos reales de P2 con las particiones de entrenamiento."
)


@app.command()
def main(
    sample_size: Annotated[
        int, typer.Option(min=2, help="Muestra total entre Train y Test.")
    ] = 15000,
    data_path: Annotated[
        Path | None, typer.Option(help="Parquet procesado de P2.")
    ] = None,
    output_dir: Annotated[
        Path, typer.Option(help="Directorio de informes HTML y JSON.")
    ] = REPORTS_DIR,
):
    """Conserva los hallazgos en los informes y señala los fallos con el código de salida."""
    started = time.monotonic()
    parquet_path = data_path or P2_FEATURES_TARGET_PARQUET
    try:
        train, test, features = load_dataset_samples(parquet_path, sample_size)
    except (FileNotFoundError, ValueError) as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=2) from error
    typer.echo(f"Dataset real: {parquet_path.name}")
    typer.echo(
        f"Train: {len(train)} filas | Test: {len(test)} filas | Features: {len(features)}"
    )
    integrity = run_data_integrity_suite(
        pd.concat([train, test]),
        features,
        output_dir / "deepchecks_data_integrity.html",
    )
    drift = run_train_test_drift_suite(
        train, test, features, output_dir / "deepchecks_data_drift.html"
    )
    suites = {"data_integrity": integrity, "train_test_drift": drift}
    summary = {
        "timestamp": datetime.now(UTC).isoformat(),
        "dataset": parquet_path.name,
        "dataset_sha256": file_sha256(parquet_path),
        "data_source": "real_parquet",
        "random_seed": 42,
        "train_samples": len(train),
        "test_samples": len(test),
        "features_evaluated": len(features),
        "feature_columns": features,
        "preparation": {
            "function": "src.features.p2_features.get_train_test_data",
            "train_timestamp_strictly_before": TRAIN_CUTOFF_DATE,
            "test_timestamp_from": TRAIN_END_DATE,
            "valid_targets": [0, 1, 2],
            "datetime_metadata": "timestamp",
            "index_metadata": "station_id|timestamp",
        },
        "versions": {
            name: version(name)
            for name in ["deepchecks", "numpy", "pandas", "scikit-learn", "setuptools"]
        },
        "python_version": platform.python_version(),
        "elapsed_seconds": round(time.monotonic() - started, 2),
        "suites": suites,
        "all_passed": all(suite["all_passed"] for suite in suites.values()),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "deepchecks_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    for name, suite in suites.items():
        status = "PASS" if suite["all_passed"] else "FAIL"
        typer.echo(
            f"{name}: {status} | checks={suite['total_checks']} | no ejecutados={len(suite['not_run_checks'])}"
        )
        for check in suite["not_passed_checks"]:
            typer.echo(f"  Condición incumplida: {check}")
        for check in suite["not_run_checks"]:
            typer.echo(f"  Error: {check['check']}: {check['reason']}")
    typer.echo(
        f"Informes guardados en {output_dir}; all_passed={summary['all_passed']}"
    )
    if not summary["all_passed"]:
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
