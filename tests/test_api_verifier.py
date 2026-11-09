"""Regresiones del código de salida y la evidencia del verificador."""

import json
import subprocess

import pytest

from scripts import verify_container_api as verifier


@pytest.mark.parametrize("status, expected", [("PASS", 0), ("FAIL", 1)])
def test_verifier_cli_propagates_result(monkeypatch, tmp_path, status, expected):
    result = {
        "overall_status": status,
        "summary": {"passed": int(status == "PASS"), "total": 1},
        "evidence_scope": "http_only",
    }
    monkeypatch.setattr(verifier, "run_checks", lambda *args: result)
    output = tmp_path / "report.json"
    assert verifier.main(["--output-json", str(output)]) == expected
    assert json.loads(output.read_text())["overall_status"] == status


@pytest.mark.parametrize(
    "running, ports, expected",
    [
        (True, {"8000/tcp": [{"HostPort": "8000"}]}, True),
        (False, {"8000/tcp": [{"HostPort": "8000"}]}, False),
        (True, {"8000/tcp": [{"HostPort": "9000"}]}, False),
    ],
)
def test_container_evidence_requires_running_service_and_matching_port(
    monkeypatch, running, ports, expected
):
    item = {
        "Id": "container-id",
        "State": {"Running": running},
        "NetworkSettings": {"Ports": ports},
    }
    monkeypatch.setattr(
        verifier.subprocess,
        "run",
        lambda *a, **k: subprocess.CompletedProcess(a, 0, stdout=json.dumps([item])),
    )
    assert (
        verifier.inspect_container("podman", "mibici-risk-service", 8000)["passed"]
        is expected
    )


@pytest.mark.parametrize("port", ["5000", "5001"])
def test_make_uses_same_mlflow_port_for_server_and_container(port):
    result = subprocess.run(
        [
            "make",
            "-n",
            "mlflow",
            "build_container",
            "run_container",
            f"MLFLOW_PORT={port}",
            "CONTAINER_ENGINE=podman",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    assert f"--port {port}" in result.stdout
    assert "build --format=docker" in result.stdout
    assert (
        f"MLFLOW_TRACKING_URI=http://host.containers.internal:{port}" in result.stdout
    )
