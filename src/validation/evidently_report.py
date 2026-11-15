"""Evidently report for P2 reference and current feature distributions."""

from pathlib import Path

import pandas as pd
from evidently import Report
from evidently.presets import DataDriftPreset, DataSummaryPreset


def generate_evidently_report(
    reference_data: pd.DataFrame,
    current_data: pd.DataFrame,
    feature_columns: list[str],
    output_html: Path,
    output_json: Path,
):
    """Generate drift and data-quality reports for the selected P2 features."""
    if not feature_columns:
        raise ValueError("Se requiere al menos una variable para el reporte.")

    for name, frame in (
        ("Referencia", reference_data),
        ("Actual", current_data),
    ):
        if frame.empty:
            raise ValueError(f"El conjunto {name.lower()} está vacío.")
        missing = sorted(set(feature_columns) - set(frame.columns))
        if missing:
            raise ValueError(
                f"Faltan variables predictoras en el conjunto {name.lower()}: "
                f"{', '.join(missing)}"
            )

    reference = reference_data.loc[:, feature_columns].copy()
    current = current_data.loc[:, feature_columns].copy()
    report = Report(
        metrics=[DataDriftPreset(), DataSummaryPreset()],
        include_tests=True,
    )
    snapshot = report.run(current_data=current, reference_data=reference)

    output_html.parent.mkdir(parents=True, exist_ok=True)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    snapshot.save_html(str(output_html))
    snapshot.save_json(str(output_json))
    return snapshot
