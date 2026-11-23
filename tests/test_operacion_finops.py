"""Pruebas unitarias para Orquestación Compose, Locust y Análisis FinOps (Semana 10)."""

from __future__ import annotations

import ast
import importlib
from pathlib import Path

import yaml

from load_tests.payloads import build_station_payload
from scripts.finops_analysis import CLOUD_PROFILES, compute_profile_costs
from scripts.run_load_and_monitor import parse_mem_mib, parse_percent


def test_docker_compose_has_required_services_networks_and_healthchecks():
    compose_path = Path("docker-compose.yml")
    assert compose_path.exists()
    config = yaml.safe_load(compose_path.read_text(encoding="utf-8"))

    assert "mlflow" in config["services"]
    assert "api" in config["services"]
    assert "mlflow_data" in config["volumes"]
    assert "mibici_net" in config["networks"]

    api_svc = config["services"]["api"]
    assert api_svc["depends_on"]["mlflow"]["condition"] == "service_healthy"
    assert "healthcheck" in api_svc
    assert "healthcheck" in config["services"]["mlflow"]
    assert api_svc["environment"]["MLFLOW_TRACKING_URI"] == "http://mlflow:5000"


def test_github_actions_workflow_exists_and_covers_ci_cd():
    wf_path = Path(".github/workflows/ci-cd.yml")
    assert wf_path.exists()
    wf = yaml.safe_load(wf_path.read_text(encoding="utf-8"))

    assert "test-suite" in wf["jobs"]
    assert "build-and-validate-compose" in wf["jobs"]
    assert wf["jobs"]["build-and-validate-compose"]["needs"] == "test-suite"


def test_locustfile_is_valid_python_with_dispatcher_user():
    locust_src = Path("load_tests/locustfile.py").read_text(encoding="utf-8")
    tree = ast.parse(locust_src)
    classes = {node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)}
    assert "MiBiciDispatcherUser" in classes


def test_locust_payload_profiles_validate_against_api_schema(monkeypatch):
    loader = importlib.import_module("api.model_loader")
    monkeypatch.setattr(loader, "load_model", lambda: object())
    api_module = importlib.reload(importlib.import_module("api.main"))
    prediction_input = api_module.PredictionInput

    for profile in ("desabasto_peak", "saturacion_peak", "normal_valley"):
        payload = build_station_payload(profile=profile)
        validated = prediction_input(**payload)
        assert validated.capacity > 0
        assert -90 <= validated.latitude <= 90
        assert -180 <= validated.longitude <= 180


def test_docker_stats_parsers():
    assert parse_mem_mib("184.5MiB / 1GiB") == 184.5
    assert parse_mem_mib("1.5GiB / 2GiB") == 1536.0
    assert parse_mem_mib("512KiB / 1GiB") == 0.5
    assert parse_percent("42.75%") == 42.75


def test_finops_right_sizing_and_scheduled_reduce_cost():
    by_key = {p.key: p for p in CLOUD_PROFILES}
    base = compute_profile_costs(by_key["fargate_x86_baseline"], 10_000_000, 12.0, 150.0)
    rightsized = compute_profile_costs(by_key["fargate_arm_rightsized"], 10_000_000, 12.0, 150.0)
    scheduled = compute_profile_costs(by_key["fargate_arm_scheduled"], 10_000_000, 12.0, 150.0)
    serverless = compute_profile_costs(by_key["cloudrun_serverless"], 3_000_000, 12.0, 150.0)

    assert base["total_monthly_usd"] > rightsized["total_monthly_usd"] > scheduled["total_monthly_usd"]
    assert base["cost_per_1m_usd"] > rightsized["cost_per_1m_usd"] > scheduled["cost_per_1m_usd"]
    assert serverless["total_monthly_usd"] > 0
    assert serverless["cost_per_inference_usd"] > 0
