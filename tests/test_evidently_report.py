"""Pruebas del reporte Evidently de drift y calidad para P2."""

import json

import numpy as np
import pandas as pd
import pytest
from typer.testing import CliRunner

from scripts.run_evidently import app
from src.validation.evidently_report import generate_evidently_report


def test_evidently_report_writes_html_and_json(tmp_path):
    reference = pd.DataFrame(
        {
            "flow": np.arange(200, dtype=float),
            "capacity": np.arange(200, dtype=float) + 10,
        }
    )
    current = reference.copy()
    current["flow"] += 100
    current.loc[0, "flow"] = np.nan
    html_path = tmp_path / "report.html"
    json_path = tmp_path / "report.json"

    snapshot = generate_evidently_report(
        reference,
        current,
        ["flow", "capacity"],
        html_path,
        json_path,
    )

    assert html_path.is_file()
    assert json_path.is_file()
    assert "Data Drift" in html_path.read_text(encoding="utf-8")
    report_data = json.loads(json_path.read_text(encoding="utf-8"))
    metric_names = [metric["metric_name"] for metric in report_data["metrics"]]
    assert any(name.startswith("ValueDrift(") for name in metric_names)
    assert "DatasetMissingValueCount()" in metric_names
    assert snapshot.json()


def test_evidently_report_rejects_missing_feature(tmp_path):
    frame = pd.DataFrame({"feature": [1.0, 2.0]})

    with pytest.raises(ValueError, match="Faltan variables"):
        generate_evidently_report(
            frame,
            frame,
            ["missing"],
            tmp_path / "report.html",
            tmp_path / "report.json",
        )


def test_evidently_cli_writes_period_summary(tmp_path, monkeypatch):
    import scripts.run_evidently as cli

    reference = pd.DataFrame({"feature": [1.0, 2.0]})
    current = pd.DataFrame({"feature": [3.0, 4.0]})
    monkeypatch.setattr(
        cli,
        "load_dataset_samples",
        lambda *args, **kwargs: (reference, current, ["feature"]),
    )
    monkeypatch.setattr(cli, "file_sha256", lambda _: "fixture-sha256")
    monkeypatch.setattr(cli, "generate_evidently_report", lambda *args, **kwargs: None)

    result = CliRunner().invoke(
        app,
        ["--data-path", "fixture.parquet", "--output-dir", str(tmp_path)],
    )

    assert result.exit_code == 0, result.output
    summary = json.loads(
        (tmp_path / "p2_data_drift_summary.json").read_text(encoding="utf-8")
    )
    assert summary["reference_period"]["rule"] == "timestamp < 2025-12-31 22:00:00"
    assert summary["current_period"]["rule"] == "timestamp >= 2026-01-01 00:00:00"
    assert summary["feature_columns"] == ["feature"]
