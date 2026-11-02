"""Regresiones de preparación temporal y de detección de fallos de calidad."""

import numpy as np
import pandas as pd
import pytest
from typer.testing import CliRunner

from scripts.run_deepchecks import app
from src.features.p2_features import get_train_test_data
from src.validation.p2_checks import (
    load_dataset_samples,
    make_dataset,
    run_data_integrity_suite,
    run_train_test_drift_suite,
)


@pytest.fixture(scope="module")
def feature_frame():
    """Fixture sintética explícita: no sustituye una auditoría del Parquet real."""
    rng = np.random.default_rng(42)
    rows = 1200
    frame = pd.DataFrame(
        rng.normal(size=(rows, 5)), columns=[f"feature_{i}" for i in range(5)]
    )
    frame["station_id"] = 1
    frame["timestamp"] = pd.date_range("2025-06-01", periods=600, freq="h").append(
        pd.date_range("2026-01-01", periods=600, freq="h")
    )
    frame["target"] = np.tile([0, 1, 2], 400)
    frame["salidas_lag_168"] = rng.normal(size=rows)
    # Deben excluirse, aunque predigan perfectamente el target.
    frame["delta_net"] = frame["target"] * 20
    frame["ratio"] = frame["target"]
    frame["salidas"] = 0
    frame["llegadas"] = 0
    frame["balance_neto"] = 0
    return frame


@pytest.fixture(scope="module")
def feature_parquet(tmp_path_factory, feature_frame):
    path = tmp_path_factory.mktemp("p2_checks") / "fixture_features.parquet"
    feature_frame.to_parquet(path, index=False)
    return path


@pytest.fixture(scope="module")
def samples(feature_parquet):
    return load_dataset_samples(feature_parquet, sample_size=1200)


def test_samples_match_production_features_and_exclude_future_information(
    feature_parquet, samples
):
    train, test, features = samples
    _, _, _, _, production_features, _ = get_train_test_data(feature_parquet)
    assert features == production_features
    assert not {
        "ratio",
        "delta_net",
        "salidas",
        "llegadas",
        "balance_neto",
        "target",
    }.intersection(features)
    assert len(train) == len(test) == 600


def test_samples_exclude_cutoff_hours_warmup_and_invalid_targets(
    tmp_path, feature_frame
):
    boundary = feature_frame.head(7).copy()
    boundary["timestamp"] = pd.to_datetime(
        [
            "2025-12-31 20:00",
            "2025-12-31 21:00",
            "2025-12-31 22:00",
            "2025-12-31 23:00",
            "2026-01-01 00:00",
            "2026-01-01 01:00",
            "2026-01-01 02:00",
        ]
    )
    boundary.loc[boundary.index[0], "salidas_lag_168"] = np.nan
    boundary.loc[boundary.index[-1], "target"] = -1
    path = tmp_path / "boundary.parquet"
    boundary.to_parquet(path, index=False)
    train, test, _ = load_dataset_samples(path, sample_size=100)
    assert train.timestamp.tolist() == [pd.Timestamp("2025-12-31 21:00")]
    assert test.timestamp.tolist() == [
        pd.Timestamp("2026-01-01 00:00"),
        pd.Timestamp("2026-01-01 01:00"),
    ]
    assert set(pd.concat([train, test]).target).issubset({0, 1, 2})


def test_sampling_is_reproducible_and_preserves_odd_requested_size(feature_parquet):
    first = load_dataset_samples(feature_parquet, sample_size=101)
    second = load_dataset_samples(feature_parquet, sample_size=101)
    pd.testing.assert_frame_equal(first[0], second[0])
    pd.testing.assert_frame_equal(first[1], second[1])
    assert [len(first[0]), len(first[1])] == [50, 51]


@pytest.mark.parametrize("sample_size", [0, 1, -2])
def test_sampling_rejects_invalid_sizes(feature_parquet, sample_size):
    with pytest.raises(ValueError, match="al menos 2"):
        load_dataset_samples(feature_parquet, sample_size=sample_size)


def test_sampling_rejects_missing_data(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_dataset_samples(tmp_path / "missing.parquet")


def test_sampling_rejects_empty_temporal_partition(tmp_path, feature_frame):
    path = tmp_path / "only_train.parquet"
    feature_frame.iloc[:600].to_parquet(path, index=False)
    with pytest.raises(ValueError, match="Train.*Test"):
        load_dataset_samples(path)


def test_dataset_preserves_datetime_and_station_hour_identity(samples):
    train, test, features = samples
    dataset = make_dataset(train, features, "fixture")
    assert dataset.datetime_col.equals(train.timestamp)
    assert dataset.index_col.is_unique
    assert set(dataset.features) == set(features)
    assert not set(dataset.index_col).intersection(
        make_dataset(test, features, "test").index_col
    )


def test_integrity_suite_really_passes_on_clean_fixture(samples):
    train, test, features = samples
    result = run_data_integrity_suite(pd.concat([train, test]), features)
    assert result["all_passed"], result
    assert result["not_run_checks"] == []


def test_temporal_suite_really_passes_on_clean_fixture(samples):
    train, test, features = samples
    result = run_train_test_drift_suite(train, test, features)
    assert result["all_passed"], result
    assert result["not_run_checks"] == []


def test_integrity_suite_detects_duplicate_rows(samples):
    train, _, features = samples
    duplicated = pd.concat([train, train.iloc[:200]])
    result = run_data_integrity_suite(duplicated, features)
    assert not result["all_passed"]
    assert "Data Duplicates" in result["not_passed_checks"]


def test_temporal_suite_detects_drift(samples):
    train, test, features = samples
    shifted = test.copy()
    shifted[features[0]] += 50
    result = run_train_test_drift_suite(train, shifted, features)
    assert not result["all_passed"]
    assert "Feature Drift" in result["not_passed_checks"]


def test_cli_writes_failure_summary_and_returns_nonzero(
    feature_parquet, tmp_path, monkeypatch
):
    import scripts.run_deepchecks as cli

    def failed_suite(*args, **kwargs):
        return {
            "all_passed": False,
            "total_checks": 1,
            "not_passed_checks": ["Injected regression"],
            "not_run_checks": [],
        }

    monkeypatch.setattr(cli, "run_data_integrity_suite", failed_suite)
    monkeypatch.setattr(cli, "run_train_test_drift_suite", failed_suite)
    result = CliRunner().invoke(
        app,
        [
            "--data-path",
            str(feature_parquet),
            "--sample-size",
            "100",
            "--output-dir",
            str(tmp_path),
        ],
    )
    assert result.exit_code == 1, result.output
    assert '"all_passed": false' in (tmp_path / "deepchecks_summary.json").read_text()
    assert "Injected regression" in result.output


def test_html_report_replaces_requested_path_without_numbered_copies(samples, tmp_path):
    train, _, features = samples
    destination = tmp_path / "integrity.html"
    destination.write_text("previous report")
    result = run_data_integrity_suite(train, features, destination)
    assert result["all_passed"], result
    assert "previous report" not in destination.read_text()
    assert list(tmp_path.glob("*.html")) == [destination]
