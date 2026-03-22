"""Tests for rqm_braket.api — Flask Blueprint endpoints.

Covers:
- POST /run (local backend, offline-safe)
- POST /run (device backend, mocked)
- POST /run/async (mocked)
- GET /tasks/<task_arn>/status (mocked)
- GET /tasks/<task_arn>/result (mocked)
- GET /devices (mocked)
- Validation errors (missing fields, bad inputs)
- BraketDeviceError → 502 responses
"""

from __future__ import annotations

import json
from collections import Counter
from unittest.mock import MagicMock, patch

import pytest
from flask import Flask

from rqm_braket.api import api_blueprint
from rqm_braket.execution import BraketDeviceError


# ---------------------------------------------------------------------------
# App fixture
# ---------------------------------------------------------------------------


@pytest.fixture()
def app() -> Flask:
    """Create a Flask test application with the rqm_braket blueprint mounted."""
    flask_app = Flask(__name__)
    flask_app.config["TESTING"] = True
    flask_app.register_blueprint(api_blueprint, url_prefix="/v1")
    return flask_app


@pytest.fixture()
def client(app: Flask):
    return app.test_client()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

BELL_DESCRIPTORS = [
    {"gate": "h", "targets": [0], "controls": [], "params": {}},
    {"gate": "cx", "targets": [1], "controls": [0], "params": {}},
]


def _make_mock_aws(
    task_id: str = "arn:aws:braket:us-east-1:123456789012:task/fake",
    counts: dict[str, int] | None = None,
) -> tuple[MagicMock, MagicMock]:
    """Return (mock_braket_aws_module, mock_task)."""
    counts = counts or {"00": 70, "11": 30}
    mock_result = MagicMock()
    mock_result.measurement_counts = Counter(counts)
    mock_result.measurement_probabilities = None
    mock_result.task_metadata = None

    mock_task = MagicMock()
    mock_task.result.return_value = mock_result
    mock_task.id = task_id

    mock_device = MagicMock()
    mock_device.run.return_value = mock_task

    mock_aws = MagicMock()
    mock_aws.AwsDevice = MagicMock(return_value=mock_device)

    mock_quantum_task = MagicMock()
    mock_quantum_task.state.return_value = "COMPLETED"
    mock_quantum_task.result.return_value = mock_result
    mock_aws.AwsQuantumTask = MagicMock(return_value=mock_quantum_task)

    return mock_aws, mock_task


# ---------------------------------------------------------------------------
# POST /v1/run — local backend (offline-safe)
# ---------------------------------------------------------------------------


def test_run_local_returns_200(client) -> None:
    """POST /v1/run with local backend returns HTTP 200."""
    resp = client.post(
        "/v1/run",
        json={"descriptors": BELL_DESCRIPTORS, "shots": 100, "backend": "local"},
    )
    assert resp.status_code == 200


def test_run_local_response_contains_counts(client) -> None:
    """POST /v1/run response includes 'counts' dict."""
    resp = client.post(
        "/v1/run",
        json={"descriptors": BELL_DESCRIPTORS, "shots": 100, "backend": "local"},
    )
    data = resp.get_json()
    assert "counts" in data
    assert isinstance(data["counts"], dict)


def test_run_local_response_contains_shots(client) -> None:
    """POST /v1/run response includes correct 'shots' value."""
    resp = client.post(
        "/v1/run",
        json={"descriptors": BELL_DESCRIPTORS, "shots": 50, "backend": "local"},
    )
    data = resp.get_json()
    assert data["shots"] == 50


def test_run_local_response_contains_probabilities(client) -> None:
    """POST /v1/run response includes 'probabilities' dict."""
    resp = client.post(
        "/v1/run",
        json={"descriptors": BELL_DESCRIPTORS, "shots": 100},
    )
    data = resp.get_json()
    assert "probabilities" in data
    total = sum(data["probabilities"].values())
    assert abs(total - 1.0) < 1e-9


def test_run_local_bell_outcomes(client) -> None:
    """POST /v1/run with Bell circuit produces only '00' and '11'."""
    resp = client.post(
        "/v1/run",
        json={"descriptors": BELL_DESCRIPTORS, "shots": 200},
    )
    data = resp.get_json()
    unexpected = set(data["counts"].keys()) - {"00", "11"}
    assert not unexpected


def test_run_local_default_backend(client) -> None:
    """POST /v1/run uses local backend by default (no backend field)."""
    resp = client.post(
        "/v1/run",
        json={"descriptors": BELL_DESCRIPTORS, "shots": 20},
    )
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# POST /v1/run — validation errors
# ---------------------------------------------------------------------------


def test_run_missing_descriptors_returns_400(client) -> None:
    """POST /v1/run without descriptors returns HTTP 400."""
    resp = client.post("/v1/run", json={"shots": 100})
    assert resp.status_code == 400
    data = resp.get_json()
    assert "error" in data


def test_run_empty_descriptors_returns_400(client) -> None:
    """POST /v1/run with empty descriptors list returns HTTP 400."""
    resp = client.post("/v1/run", json={"descriptors": []})
    assert resp.status_code == 400


def test_run_no_body_returns_400(client) -> None:
    """POST /v1/run with no JSON body returns HTTP 400."""
    resp = client.post("/v1/run", content_type="application/json", data="{}")
    assert resp.status_code == 400


def test_run_device_backend_missing_device_arn_returns_400(client) -> None:
    """POST /v1/run with device backend but no device_arn returns HTTP 400."""
    resp = client.post(
        "/v1/run",
        json={
            "descriptors": BELL_DESCRIPTORS,
            "backend": "device",
            "s3_folder": ["bucket", "prefix"],
        },
    )
    assert resp.status_code == 400


def test_run_device_backend_missing_s3_folder_returns_400(client) -> None:
    """POST /v1/run with device backend but no s3_folder returns HTTP 400."""
    resp = client.post(
        "/v1/run",
        json={
            "descriptors": BELL_DESCRIPTORS,
            "backend": "device",
            "device_arn": "arn:aws:braket:::device/quantum-simulator/amazon/sv1",
        },
    )
    assert resp.status_code == 400


def test_run_invalid_backend_returns_400(client) -> None:
    """POST /v1/run with unknown backend value returns HTTP 400."""
    resp = client.post(
        "/v1/run",
        json={"descriptors": BELL_DESCRIPTORS, "backend": "quantum-cloud"},
    )
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_run_invalid_s3_folder_length_returns_400(client) -> None:
    """POST /v1/run with s3_folder of wrong length returns HTTP 400."""
    resp = client.post(
        "/v1/run",
        json={
            "descriptors": BELL_DESCRIPTORS,
            "backend": "device",
            "device_arn": "arn:aws:braket:::device/quantum-simulator/amazon/sv1",
            "s3_folder": ["only-one-element"],
        },
    )
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# POST /v1/run — device backend (mocked)
# ---------------------------------------------------------------------------


def test_run_device_backend_returns_200(client) -> None:
    """POST /v1/run with device backend (mocked) returns HTTP 200."""
    mock_aws, _ = _make_mock_aws()
    with patch.dict("sys.modules", {"braket.aws": mock_aws}):
        resp = client.post(
            "/v1/run",
            json={
                "descriptors": BELL_DESCRIPTORS,
                "shots": 100,
                "backend": "device",
                "device_arn": "arn:aws:braket:::device/quantum-simulator/amazon/sv1",
                "s3_folder": ["my-bucket", "my-prefix"],
            },
        )
    assert resp.status_code == 200
    data = resp.get_json()
    assert "counts" in data


def test_run_device_error_returns_502(client) -> None:
    """POST /v1/run device backend failure returns HTTP 502."""
    mock_aws = MagicMock()
    mock_aws.AwsDevice = MagicMock(side_effect=RuntimeError("network error"))
    with patch.dict("sys.modules", {"braket.aws": mock_aws}):
        resp = client.post(
            "/v1/run",
            json={
                "descriptors": BELL_DESCRIPTORS,
                "shots": 100,
                "backend": "device",
                "device_arn": "arn:aws:braket:::device/quantum-simulator/amazon/sv1",
                "s3_folder": ["my-bucket", "my-prefix"],
            },
        )
    assert resp.status_code == 502
    assert "error" in resp.get_json()


# ---------------------------------------------------------------------------
# POST /v1/run/async — asynchronous submission
# ---------------------------------------------------------------------------

TASK_ARN = "arn:aws:braket:us-east-1:123456789012:task/fake-task-id"


def test_run_async_returns_202(client) -> None:
    """POST /v1/run/async returns HTTP 202 Accepted."""
    mock_aws, _ = _make_mock_aws(task_id=TASK_ARN)
    with patch.dict("sys.modules", {"braket.aws": mock_aws}):
        resp = client.post(
            "/v1/run/async",
            json={
                "descriptors": BELL_DESCRIPTORS,
                "shots": 100,
                "device_arn": "arn:aws:braket:::device/quantum-simulator/amazon/sv1",
                "s3_folder": ["my-bucket", "my-prefix"],
            },
        )
    assert resp.status_code == 202


def test_run_async_returns_task_arn(client) -> None:
    """POST /v1/run/async response body contains 'task_arn'."""
    mock_aws, _ = _make_mock_aws(task_id=TASK_ARN)
    with patch.dict("sys.modules", {"braket.aws": mock_aws}):
        resp = client.post(
            "/v1/run/async",
            json={
                "descriptors": BELL_DESCRIPTORS,
                "shots": 100,
                "device_arn": "arn:aws:braket:::device/quantum-simulator/amazon/sv1",
                "s3_folder": ["my-bucket", "my-prefix"],
            },
        )
    data = resp.get_json()
    assert "task_arn" in data
    assert data["task_arn"] == TASK_ARN


def test_run_async_missing_descriptors_returns_400(client) -> None:
    """POST /v1/run/async without descriptors returns HTTP 400."""
    resp = client.post(
        "/v1/run/async",
        json={"device_arn": "arn:...", "s3_folder": ["b", "p"]},
    )
    assert resp.status_code == 400


def test_run_async_missing_device_arn_returns_400(client) -> None:
    """POST /v1/run/async without device_arn returns HTTP 400."""
    resp = client.post(
        "/v1/run/async",
        json={"descriptors": BELL_DESCRIPTORS, "s3_folder": ["b", "p"]},
    )
    assert resp.status_code == 400


def test_run_async_missing_s3_folder_returns_400(client) -> None:
    """POST /v1/run/async without s3_folder returns HTTP 400."""
    resp = client.post(
        "/v1/run/async",
        json={"descriptors": BELL_DESCRIPTORS, "device_arn": "arn:..."},
    )
    assert resp.status_code == 400


def test_run_async_invalid_s3_folder_returns_400(client) -> None:
    """POST /v1/run/async with s3_folder of wrong length returns HTTP 400."""
    resp = client.post(
        "/v1/run/async",
        json={
            "descriptors": BELL_DESCRIPTORS,
            "device_arn": "arn:...",
            "s3_folder": ["only-one-element"],
        },
    )
    assert resp.status_code == 400


def test_run_async_device_error_returns_502(client) -> None:
    """POST /v1/run/async device failure returns HTTP 502."""
    mock_aws = MagicMock()
    mock_aws.AwsDevice = MagicMock(side_effect=RuntimeError("connection refused"))
    with patch.dict("sys.modules", {"braket.aws": mock_aws}):
        resp = client.post(
            "/v1/run/async",
            json={
                "descriptors": BELL_DESCRIPTORS,
                "device_arn": "arn:aws:braket:::device/quantum-simulator/amazon/sv1",
                "s3_folder": ["b", "p"],
            },
        )
    assert resp.status_code == 502
    assert "error" in resp.get_json()


# ---------------------------------------------------------------------------
# GET /v1/tasks/<task_arn>/status
# ---------------------------------------------------------------------------


def test_task_status_returns_200(client) -> None:
    """GET /v1/tasks/<arn>/status returns HTTP 200."""
    mock_aws, _ = _make_mock_aws()
    with patch.dict("sys.modules", {"braket.aws": mock_aws}):
        resp = client.get(f"/v1/tasks/{TASK_ARN}/status")
    assert resp.status_code == 200


def test_task_status_response_body(client) -> None:
    """GET /v1/tasks/<arn>/status response contains task_arn and status."""
    mock_aws, _ = _make_mock_aws()
    with patch.dict("sys.modules", {"braket.aws": mock_aws}):
        resp = client.get(f"/v1/tasks/{TASK_ARN}/status")
    data = resp.get_json()
    assert data["task_arn"] == TASK_ARN
    assert data["status"] == "COMPLETED"


def test_task_status_queued(client) -> None:
    """GET /v1/tasks/<arn>/status returns QUEUED when task is queued."""
    mock_aws = MagicMock()
    mock_task_obj = MagicMock()
    mock_task_obj.state.return_value = "QUEUED"
    mock_aws.AwsQuantumTask = MagicMock(return_value=mock_task_obj)
    with patch.dict("sys.modules", {"braket.aws": mock_aws}):
        resp = client.get(f"/v1/tasks/{TASK_ARN}/status")
    data = resp.get_json()
    assert data["status"] == "QUEUED"


def test_task_status_error_returns_502(client) -> None:
    """GET /v1/tasks/<arn>/status returns HTTP 502 on device error."""
    mock_aws = MagicMock()
    mock_aws.AwsQuantumTask = MagicMock(side_effect=RuntimeError("not found"))
    with patch.dict("sys.modules", {"braket.aws": mock_aws}):
        resp = client.get(f"/v1/tasks/{TASK_ARN}/status")
    assert resp.status_code == 502
    assert "error" in resp.get_json()


# ---------------------------------------------------------------------------
# GET /v1/tasks/<task_arn>/result
# ---------------------------------------------------------------------------


def test_task_result_returns_200(client) -> None:
    """GET /v1/tasks/<arn>/result returns HTTP 200."""
    mock_aws, _ = _make_mock_aws(counts={"00": 60, "11": 40})
    with patch.dict("sys.modules", {"braket.aws": mock_aws}):
        resp = client.get(f"/v1/tasks/{TASK_ARN}/result")
    assert resp.status_code == 200


def test_task_result_contains_counts(client) -> None:
    """GET /v1/tasks/<arn>/result response includes counts and shots."""
    mock_aws, _ = _make_mock_aws(counts={"00": 60, "11": 40})
    with patch.dict("sys.modules", {"braket.aws": mock_aws}):
        resp = client.get(f"/v1/tasks/{TASK_ARN}/result")
    data = resp.get_json()
    assert "counts" in data
    assert data["shots"] == 100


def test_task_result_contains_probabilities(client) -> None:
    """GET /v1/tasks/<arn>/result response includes probabilities."""
    mock_aws, _ = _make_mock_aws()
    with patch.dict("sys.modules", {"braket.aws": mock_aws}):
        resp = client.get(f"/v1/tasks/{TASK_ARN}/result")
    data = resp.get_json()
    assert "probabilities" in data


def test_task_result_error_returns_502(client) -> None:
    """GET /v1/tasks/<arn>/result returns HTTP 502 on device error."""
    mock_aws = MagicMock()
    mock_aws.AwsQuantumTask = MagicMock(side_effect=RuntimeError("task failed"))
    with patch.dict("sys.modules", {"braket.aws": mock_aws}):
        resp = client.get(f"/v1/tasks/{TASK_ARN}/result")
    assert resp.status_code == 502
    assert "error" in resp.get_json()


# ---------------------------------------------------------------------------
# GET /v1/devices
# ---------------------------------------------------------------------------


def _make_mock_device(
    arn: str = "arn:aws:braket:::device/quantum-simulator/amazon/sv1",
    name: str = "SV1",
    device_type: str = "SIMULATOR",
    status: str = "ONLINE",
    provider: str = "Amazon",
) -> MagicMock:
    dev = MagicMock()
    dev.arn = arn
    dev.name = name
    dev.type = MagicMock()
    dev.type.value = device_type
    dev.status = status
    dev.provider_name = provider
    return dev


def test_devices_returns_200(client) -> None:
    """GET /v1/devices returns HTTP 200."""
    mock_aws = MagicMock()
    mock_aws.AwsDevice.get_devices.return_value = [_make_mock_device()]
    with patch.dict("sys.modules", {"braket.aws": mock_aws}):
        resp = client.get("/v1/devices")
    assert resp.status_code == 200


def test_devices_response_contains_devices_list(client) -> None:
    """GET /v1/devices response body has a 'devices' list."""
    mock_dev = _make_mock_device()
    mock_aws = MagicMock()
    mock_aws.AwsDevice.get_devices.return_value = [mock_dev]
    with patch.dict("sys.modules", {"braket.aws": mock_aws}):
        resp = client.get("/v1/devices")
    data = resp.get_json()
    assert "devices" in data
    assert isinstance(data["devices"], list)
    assert len(data["devices"]) == 1


def test_devices_response_entry_shape(client) -> None:
    """GET /v1/devices response entries have expected keys."""
    mock_dev = _make_mock_device(
        arn="arn:aws:braket:::device/quantum-simulator/amazon/sv1",
        name="SV1",
        device_type="SIMULATOR",
        status="ONLINE",
        provider="Amazon",
    )
    mock_aws = MagicMock()
    mock_aws.AwsDevice.get_devices.return_value = [mock_dev]
    with patch.dict("sys.modules", {"braket.aws": mock_aws}):
        resp = client.get("/v1/devices")
    entry = resp.get_json()["devices"][0]
    assert entry["deviceArn"] == "arn:aws:braket:::device/quantum-simulator/amazon/sv1"
    assert entry["deviceName"] == "SV1"
    assert entry["deviceType"] == "SIMULATOR"
    assert entry["status"] == "ONLINE"
    assert entry["providerName"] == "Amazon"


def test_devices_type_filter(client) -> None:
    """GET /v1/devices?type=SIMULATOR passes type filter to list_devices."""
    mock_aws = MagicMock()
    mock_aws.AwsDevice.get_devices.return_value = []
    with patch.dict("sys.modules", {"braket.aws": mock_aws}):
        resp = client.get("/v1/devices?type=SIMULATOR")
    assert resp.status_code == 200
    call_kwargs = mock_aws.AwsDevice.get_devices.call_args[1]
    assert "SIMULATOR" in call_kwargs.get("types", [])


def test_devices_error_returns_502(client) -> None:
    """GET /v1/devices returns HTTP 502 when listing fails."""
    mock_aws = MagicMock()
    mock_aws.AwsDevice.get_devices.side_effect = RuntimeError("credentials missing")
    with patch.dict("sys.modules", {"braket.aws": mock_aws}):
        resp = client.get("/v1/devices")
    assert resp.status_code == 502
    assert "error" in resp.get_json()


# ---------------------------------------------------------------------------
# Blueprint registration
# ---------------------------------------------------------------------------


def test_api_blueprint_importable() -> None:
    """api_blueprint is importable from rqm_braket.api."""
    from rqm_braket.api import api_blueprint as bp

    assert bp is not None


def test_api_blueprint_exportable_from_package() -> None:
    """api_blueprint is re-exported from the rqm_braket package."""
    from rqm_braket import api_blueprint as bp

    assert bp is not None
