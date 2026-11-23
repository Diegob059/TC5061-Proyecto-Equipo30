"""Regresiones de costo, fallos de ejecución y versión realmente cargada."""
from __future__ import annotations

import json
import subprocess
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

from api import model_loader as loader
from scripts import finops_analysis as finops
from scripts import run_load_and_monitor as runner


def test_model_alias_is_pinned_and_metadata_survives_alias_change(monkeypatch):
    current = SimpleNamespace(version="7", run_id="run-7")
    client = SimpleNamespace(
        get_model_version_by_alias=lambda name, alias: current,
        get_run=lambda rid: SimpleNamespace(data=SimpleNamespace(tags={"origin": "replicated_from:training"})),
    )
    loaded_uris = []
    model = SimpleNamespace(metadata=SimpleNamespace(run_id="run-7", model_uuid="model-7"))
    monkeypatch.setattr(loader, "MODEL_URI", "models:/risk@champion")
    monkeypatch.setattr(loader, "_loaded_metadata", {})
    monkeypatch.setattr(loader.mlflow, "set_tracking_uri", lambda uri: None)
    monkeypatch.setattr(loader.mlflow.tracking, "MlflowClient", lambda **kw: client)
    monkeypatch.setattr(loader.mlflow.pyfunc, "load_model", lambda uri: loaded_uris.append(uri) or model)
    assert loader.load_model() is model
    current.version = "8"
    assert loaded_uris == ["models:/risk/7"]
    metadata = loader.get_model_metadata()
    assert metadata["model_version"] == "7"
    assert metadata["run_id"] == "run-7"
    assert metadata["origin"] == "replicated_from:training"
    assert metadata["resolved_model_uri"] == "models:/risk/7"
    assert metadata["provenance_status"] == "identified"


def test_monitor_records_errors_instead_of_reporting_zero(monkeypatch):
    stop, records, errors = threading.Event(), [], []
    def failed_stats(*args, **kwargs):
        stop.set()
        return subprocess.CompletedProcess(args[0], 1, stdout="", stderr="daemon unavailable")
    monkeypatch.setattr(runner.subprocess, "run", failed_stats)
    runner.sample_docker_stats(stop, records, "load", ["api"], errors=errors)
    assert not records
    assert "daemon unavailable" in errors[0]
    missing = runner.aggregate_resources(records)
    assert missing["sample_count"] == 0
    assert missing["cpu_avg_perc"] is None
    assert missing["mem_max_mib"] is None


@pytest.mark.parametrize("text", ["N/A", "", "nan%", "-1%"])
def test_invalid_percent_is_not_zero(text):
    with pytest.raises(ValueError):
        runner.parse_percent(text)


@pytest.mark.parametrize("text", ["N/A", "", "1Unknown / 1GiB"])
def test_invalid_memory_is_not_zero(text):
    with pytest.raises(ValueError):
        runner.parse_mem_mib(text)


def prepare_runner(monkeypatch, tmp_path, exit_code, create_csv=True):
    scenario = dict(name="check", label="Carga", users=1, spawn_rate=1, duration="1s")
    monkeypatch.setattr(runner, "SCENARIOS", [scenario])
    monkeypatch.setattr(runner, "discover_compose_containers", lambda *a: {"api": "a", "mlflow": "m"})
    monkeypatch.setattr(runner, "inspect_containers", lambda *a: {"api": {"name": "api"}, "mlflow": {"name": "mlflow"}})
    monkeypatch.setattr(runner, "fetch_model_metadata", lambda *a: dict(model_version="3", run_id="r3", loaded_at_utc="same"))
    class Monitor:
        def __init__(self, target, args, daemon):
            self.records, self.name = args[1:3]
        def start(self):
            for service in ("api", "mlflow"):
                self.records.append(dict(scenario=self.name, container=service, cpu_perc=1, mem_mib=20))
        def join(self):
            pass
    monkeypatch.setattr(runner.threading, "Thread", Monitor)
    def locust(cmd, **kwargs):
        if create_csv:
            prefix = cmd[cmd.index("--csv") + 1]
            Path(prefix + "_stats.csv").write_text(
                'Name,Request Count,Failure Count,Requests/s,Average Response Time,50%,95%,99%,Max Response Time\n'
                'POST /predict,10,1,9,5,5,8,9,10\nAggregated,12,1,11,5,5,8,9,10\n')
        return subprocess.CompletedProcess(cmd, exit_code, stdout="log", stderr="")
    monkeypatch.setattr(runner.subprocess, "run", locust)


def test_locust_failure_is_saved_and_cli_returns_failure(monkeypatch, tmp_path):
    prepare_runner(monkeypatch, tmp_path, 1)
    assert runner.main(["--output-dir", str(tmp_path)]) == 1
    report = json.loads((tmp_path / "load_test_summary.json").read_text())
    assert report["overall_status"] == "FAIL"
    assert report["scenarios"][0]["locust_exit_code"] == 1
    assert report["scenarios"][0]["failure_count"] == 1


def test_previous_csv_cannot_make_failed_run_pass(monkeypatch, tmp_path):
    (tmp_path / "locust_check_stats.csv").write_text("old data")
    prepare_runner(monkeypatch, tmp_path, 2, create_csv=False)
    assert runner.main(["--output-dir", str(tmp_path)]) == 1
    report = json.loads((tmp_path / "load_test_summary.json").read_text())
    assert "rps_predict" not in report["scenarios"][0]
    assert report["overall_status"] == "FAIL"


def test_synthetic_model_requires_explicit_flag(monkeypatch, tmp_path):
    prepare_runner(monkeypatch, tmp_path, 0)
    monkeypatch.setattr(runner, "fetch_model_metadata", lambda *a: dict(model_version="1", run_id="r", origin="ci_smoke_synthetic"))
    assert runner.main(["--output-dir", str(tmp_path)]) == 2
    assert not (tmp_path / "load_test_summary.json").exists()


def test_finops_uses_predict_rps_and_retains_raw_summary(monkeypatch, tmp_path):
    source = Path("reports/semana10/load_test_summary.json")
    historical = source.read_bytes()
    monkeypatch.setattr(finops, "SEMANA10_DIR", tmp_path)
    monkeypatch.setattr(finops, "generate_figures", lambda *a: [])
    report = finops.run_finops_analysis(source)
    assert report["observed_telemetry"]["sustained_rps_peak"] == 256.44
    assert report["observed_telemetry"]["extrapolated_inferences_month_730h"] == 673_924_320
    assert source.read_bytes() == historical
    assert report["observed_telemetry"]["historical_model_provenance"] == "not_recorded"


@pytest.mark.parametrize("ms, expected_seconds", [(6.82, 0.1), (100, 0.1), (101, 0.2)])
def test_cloudrun_explicit_serial_scenario_rounds_up(ms, expected_seconds):
    profile = next(p for p in finops.CLOUD_PROFILES if p.key == "cloudrun_serverless")
    row = finops.compute_profile_costs(profile, 1_000_000, ms, 256.44, 36.04)
    assert row["cloudrun_billed_seconds_per_request"] == pytest.approx(expected_seconds)
    assert row["compute_monthly_usd"] == pytest.approx(expected_seconds * 25.25 + 0.4)
    assert row["total_monthly_usd"] == pytest.approx(row["compute_monthly_usd"] + 36.04)


@pytest.mark.parametrize("n,lat,rps,cost", [(0,10,1,0), (1,0,1,0), (1,10,0,0), (1,10,1,-1), (1,float('nan'),1,0)])
def test_invalid_cost_inputs_are_rejected(n, lat, rps, cost):
    with pytest.raises(ValueError):
        finops.compute_profile_costs(finops.CLOUD_PROFILES[0], n, lat, rps, cost)


def test_real_mlflow_registry_reports_version_actually_loaded(monkeypatch, tmp_path):
    """Roundtrip local de MLflow: cambiar champion no cambia el objeto ya cargado."""
    import mlflow
    import mlflow.pyfunc
    import pandas as pd

    class ConstantRisk(mlflow.pyfunc.PythonModel):
        def __init__(self, value):
            self.value = value
        def predict(self, context, model_input, params=None):
            return [self.value] * len(model_input)

    old_uri = mlflow.get_tracking_uri()
    uri = (tmp_path / "tracking").as_uri()
    monkeypatch.setenv("MLFLOW_TRACKING_URI", uri)
    monkeypatch.setattr(loader, "MODEL_URI", "models:/risk-regression@champion")
    monkeypatch.setattr(loader, "_loaded_metadata", {})
    try:
        mlflow.set_tracking_uri(uri)
        mlflow.set_experiment("loader-roundtrip")
        client = mlflow.tracking.MlflowClient(tracking_uri=uri)
        versions = []
        for value in (1, 2):
            with mlflow.start_run() as run:
                mlflow.set_tag("origin", "regression_test_synthetic")
                info = mlflow.pyfunc.log_model(
                    name="risk", python_model=ConstantRisk(value), pip_requirements=[],
                    input_example=pd.DataFrame({"capacity": [20]}))
                version = mlflow.register_model(info.model_uri, "risk-regression")
                versions.append(version)
        client.set_registered_model_alias("risk-regression", "champion", versions[0].version)
        loaded = loader.load_model()
        client.set_registered_model_alias("risk-regression", "champion", versions[1].version)
        assert loaded.predict(pd.DataFrame({"capacity": [20]})) == [1]
        metadata = loader.get_model_metadata()
        assert metadata["model_version"] == str(versions[0].version)
        assert metadata["run_id"] == versions[0].run_id
        assert metadata["origin"] == "regression_test_synthetic"
    finally:
        mlflow.set_tracking_uri(old_uri)
