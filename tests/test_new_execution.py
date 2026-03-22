"""Tests for new execution API added in the rqm-braket execution engine update.

Covers:
- run_device_async (mocked)
- get_task_status (mocked)
- get_task_result (mocked)
- list_devices (mocked)
- run_descriptors (local, offline-safe)
- BraketDeviceError exception
- BraketResult.to_dict() optional extras
- BraketBackend.run_device_async (mocked)
- BraketBackend.run_descriptors (local, offline-safe)
"""

from __future__ import annotations

from collections import Counter
from unittest.mock import MagicMock, patch

import pytest
from braket.circuits import Circuit

from rqm_braket.backend import BraketBackend
from rqm_braket.circuits import bell_circuit
from rqm_braket.execution import (
    BraketDeviceError,
    get_task_result,
    get_task_status,
    list_devices,
    run_descriptors,
    run_device_async,
)
from rqm_braket.results import BraketResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_raw(
    counts: dict[str, int] | None = None,
    probabilities: dict[str, float] | None = None,
    task_metadata: object = None,
) -> MagicMock:
    raw = MagicMock()
    raw.measurement_counts = Counter(counts if counts is not None else {"00": 70, "11": 30})
    raw.measurement_probabilities = probabilities
    raw.task_metadata = task_metadata
    return raw


def _make_mock_aws(counts: dict[str, int]) -> tuple[MagicMock, MagicMock]:
    """Return (mock_braket_aws_module, mock_task)."""
    mock_result = MagicMock()
    mock_result.measurement_counts = Counter(counts)
    mock_result.measurement_probabilities = None
    mock_result.task_metadata = None

    mock_task = MagicMock()
    mock_task.result.return_value = mock_result
    mock_task.id = "arn:aws:braket:us-east-1:123456789012:task/fake-task-id"

    mock_device_instance = MagicMock()
    mock_device_instance.run.return_value = mock_task

    mock_aws_module = MagicMock()
    mock_aws_module.AwsDevice = MagicMock(return_value=mock_device_instance)

    return mock_aws_module, mock_task


# ---------------------------------------------------------------------------
# BraketDeviceError
# ---------------------------------------------------------------------------


def test_braket_device_error_is_runtime_error() -> None:
    """BraketDeviceError is a RuntimeError subclass."""
    exc = BraketDeviceError("test error")
    assert isinstance(exc, RuntimeError)


def test_braket_device_error_message() -> None:
    """BraketDeviceError preserves the message."""
    exc = BraketDeviceError("device unreachable")
    assert "device unreachable" in str(exc)


# ---------------------------------------------------------------------------
# run_device_async — mocked
# ---------------------------------------------------------------------------


def test_run_device_async_returns_task_arn() -> None:
    """run_device_async returns the task ARN string."""
    mock_aws, mock_task = _make_mock_aws({"00": 60, "11": 40})
    with patch.dict("sys.modules", {"braket.aws": mock_aws}):
        task_arn = run_device_async(
            bell_circuit(),
            device_arn="arn:aws:braket:::device/quantum-simulator/amazon/sv1",
            s3_folder=("bucket", "prefix"),
            shots=100,
        )
    assert isinstance(task_arn, str)
    assert task_arn == mock_task.id


def test_run_device_async_does_not_call_result() -> None:
    """run_device_async must NOT call task.result() (it is non-blocking)."""
    mock_aws, mock_task = _make_mock_aws({"00": 60, "11": 40})
    with patch.dict("sys.modules", {"braket.aws": mock_aws}):
        run_device_async(
            bell_circuit(),
            device_arn="arn:aws:braket:::device/quantum-simulator/amazon/sv1",
            s3_folder=("bucket", "prefix"),
            shots=100,
        )
    mock_task.result.assert_not_called()


def test_run_device_async_wraps_exception() -> None:
    """run_device_async raises BraketDeviceError when AwsDevice raises."""
    mock_aws = MagicMock()
    mock_aws.AwsDevice = MagicMock(side_effect=RuntimeError("network error"))
    with patch.dict("sys.modules", {"braket.aws": mock_aws}):
        with pytest.raises(BraketDeviceError, match="network error"):
            run_device_async(
                bell_circuit(),
                device_arn="arn:aws:braket:::device/quantum-simulator/amazon/sv1",
                s3_folder=("bucket", "prefix"),
            )


def test_run_device_async_translates_rqmgate_sequence() -> None:
    """run_device_async accepts an RQMGate sequence and passes a Circuit to AwsDevice."""
    from rqm_braket.translator import RQMGate

    mock_aws, _ = _make_mock_aws({"1": 100})
    mock_device_instance = mock_aws.AwsDevice.return_value
    with patch.dict("sys.modules", {"braket.aws": mock_aws}):
        run_device_async(
            [RQMGate(gate="X", target=0)],
            device_arn="arn:aws:braket:::device/quantum-simulator/amazon/sv1",
            s3_folder=("bucket", "prefix"),
            shots=50,
        )
    call_args = mock_device_instance.run.call_args
    assert isinstance(call_args[0][0], Circuit)


# ---------------------------------------------------------------------------
# get_task_status — mocked
# ---------------------------------------------------------------------------


def test_get_task_status_returns_string() -> None:
    """get_task_status returns the string status from the task."""
    mock_task = MagicMock()
    mock_task.state.return_value = "COMPLETED"

    mock_aws = MagicMock()
    mock_aws.AwsQuantumTask = MagicMock(return_value=mock_task)

    with patch.dict("sys.modules", {"braket.aws": mock_aws}):
        status = get_task_status("arn:aws:braket:us-east-1:123456789012:task/abc")

    assert status == "COMPLETED"


def test_get_task_status_queued() -> None:
    """get_task_status returns 'QUEUED' when task is queued."""
    mock_task = MagicMock()
    mock_task.state.return_value = "QUEUED"

    mock_aws = MagicMock()
    mock_aws.AwsQuantumTask = MagicMock(return_value=mock_task)

    with patch.dict("sys.modules", {"braket.aws": mock_aws}):
        status = get_task_status("arn:aws:braket:us-east-1:123456789012:task/abc")

    assert status == "QUEUED"


def test_get_task_status_wraps_exception() -> None:
    """get_task_status raises BraketDeviceError when AWS raises."""
    mock_aws = MagicMock()
    mock_aws.AwsQuantumTask = MagicMock(side_effect=RuntimeError("not found"))

    with patch.dict("sys.modules", {"braket.aws": mock_aws}):
        with pytest.raises(BraketDeviceError, match="not found"):
            get_task_status("arn:aws:braket:us-east-1:123456789012:task/bad")


# ---------------------------------------------------------------------------
# get_task_result — mocked
# ---------------------------------------------------------------------------


def test_get_task_result_returns_braket_result() -> None:
    """get_task_result returns a BraketResult wrapping the task result."""
    mock_result = MagicMock()
    mock_result.measurement_counts = Counter({"00": 60, "11": 40})
    mock_result.measurement_probabilities = None
    mock_result.task_metadata = None

    mock_task = MagicMock()
    mock_task.result.return_value = mock_result

    mock_aws = MagicMock()
    mock_aws.AwsQuantumTask = MagicMock(return_value=mock_task)

    with patch.dict("sys.modules", {"braket.aws": mock_aws}):
        result = get_task_result("arn:aws:braket:us-east-1:123456789012:task/abc")

    assert isinstance(result, BraketResult)
    assert result.shots == 100


def test_get_task_result_wraps_exception() -> None:
    """get_task_result raises BraketDeviceError when AWS raises."""
    mock_aws = MagicMock()
    mock_aws.AwsQuantumTask = MagicMock(side_effect=RuntimeError("task failed"))

    with patch.dict("sys.modules", {"braket.aws": mock_aws}):
        with pytest.raises(BraketDeviceError, match="task failed"):
            get_task_result("arn:aws:braket:us-east-1:123456789012:task/bad")


# ---------------------------------------------------------------------------
# list_devices — mocked
# ---------------------------------------------------------------------------


def _make_mock_device(
    arn: str,
    name: str,
    device_type: str,
    status: str,
    provider: str,
) -> MagicMock:
    dev = MagicMock()
    dev.arn = arn
    dev.name = name
    dev.type = MagicMock()
    dev.type.value = device_type
    dev.status = status
    dev.provider_name = provider
    return dev


def test_list_devices_returns_list() -> None:
    """list_devices returns a list of dicts."""
    mock_devices = [
        _make_mock_device(
            "arn:aws:braket:::device/quantum-simulator/amazon/sv1",
            "SV1",
            "SIMULATOR",
            "ONLINE",
            "Amazon",
        ),
    ]
    mock_aws = MagicMock()
    mock_aws.AwsDevice.get_devices.return_value = mock_devices

    with patch.dict("sys.modules", {"braket.aws": mock_aws}):
        devices = list_devices()

    assert isinstance(devices, list)
    assert len(devices) == 1


def test_list_devices_dict_has_required_keys() -> None:
    """Each device dict has the required keys."""
    mock_devices = [
        _make_mock_device(
            "arn:aws:braket:::device/quantum-simulator/amazon/sv1",
            "SV1",
            "SIMULATOR",
            "ONLINE",
            "Amazon",
        ),
    ]
    mock_aws = MagicMock()
    mock_aws.AwsDevice.get_devices.return_value = mock_devices

    with patch.dict("sys.modules", {"braket.aws": mock_aws}):
        devices = list_devices()

    device = devices[0]
    assert "deviceArn" in device
    assert "deviceName" in device
    assert "deviceType" in device
    assert "status" in device
    assert "providerName" in device


def test_list_devices_values() -> None:
    """list_devices returns the correct field values."""
    mock_devices = [
        _make_mock_device(
            "arn:aws:braket:::device/quantum-simulator/amazon/sv1",
            "SV1",
            "SIMULATOR",
            "ONLINE",
            "Amazon",
        ),
    ]
    mock_aws = MagicMock()
    mock_aws.AwsDevice.get_devices.return_value = mock_devices

    with patch.dict("sys.modules", {"braket.aws": mock_aws}):
        devices = list_devices()

    d = devices[0]
    assert d["deviceArn"] == "arn:aws:braket:::device/quantum-simulator/amazon/sv1"
    assert d["deviceName"] == "SV1"
    assert d["deviceType"] == "SIMULATOR"
    assert d["status"] == "ONLINE"
    assert d["providerName"] == "Amazon"


def test_list_devices_with_type_filter() -> None:
    """list_devices passes the type filter to AwsDevice.get_devices."""
    mock_aws = MagicMock()
    mock_aws.AwsDevice.get_devices.return_value = []

    with patch.dict("sys.modules", {"braket.aws": mock_aws}):
        list_devices(device_types=["QPU"])

    call_kwargs = mock_aws.AwsDevice.get_devices.call_args[1]
    assert "types" in call_kwargs
    assert "QPU" in call_kwargs["types"]


def test_list_devices_no_filter() -> None:
    """list_devices without filter does not pass 'types' to get_devices."""
    mock_aws = MagicMock()
    mock_aws.AwsDevice.get_devices.return_value = []

    with patch.dict("sys.modules", {"braket.aws": mock_aws}):
        list_devices()

    call_kwargs = mock_aws.AwsDevice.get_devices.call_args[1]
    assert "types" not in call_kwargs


def test_list_devices_wraps_exception() -> None:
    """list_devices raises BraketDeviceError when AWS raises."""
    mock_aws = MagicMock()
    mock_aws.AwsDevice.get_devices.side_effect = RuntimeError("no credentials")

    with patch.dict("sys.modules", {"braket.aws": mock_aws}):
        with pytest.raises(BraketDeviceError, match="no credentials"):
            list_devices()


def test_list_devices_multiple_devices() -> None:
    """list_devices handles multiple devices correctly."""
    mock_devices = [
        _make_mock_device(
            "arn:aws:braket:::device/quantum-simulator/amazon/sv1",
            "SV1",
            "SIMULATOR",
            "ONLINE",
            "Amazon",
        ),
        _make_mock_device(
            "arn:aws:braket:::device/qpu/ionq/ionQdevice",
            "IonQ Device",
            "QPU",
            "ONLINE",
            "IonQ",
        ),
    ]
    mock_aws = MagicMock()
    mock_aws.AwsDevice.get_devices.return_value = mock_devices

    with patch.dict("sys.modules", {"braket.aws": mock_aws}):
        devices = list_devices()

    assert len(devices) == 2
    names = {d["deviceName"] for d in devices}
    assert "SV1" in names
    assert "IonQ Device" in names


# ---------------------------------------------------------------------------
# run_descriptors — offline-safe (local backend)
# ---------------------------------------------------------------------------


def test_run_descriptors_local_returns_braket_result() -> None:
    """run_descriptors(backend='local') returns a BraketResult."""
    descriptors = [
        {"gate": "h", "targets": [0], "controls": [], "params": {}},
        {"gate": "cx", "targets": [1], "controls": [0], "params": {}},
    ]
    result = run_descriptors(descriptors, shots=100)
    assert isinstance(result, BraketResult)


def test_run_descriptors_local_shot_count() -> None:
    """run_descriptors shot count matches."""
    descriptors = [
        {"gate": "h", "targets": [0], "controls": [], "params": {}},
        {"gate": "cx", "targets": [1], "controls": [0], "params": {}},
    ]
    result = run_descriptors(descriptors, shots=150)
    assert result.shots == 150


def test_run_descriptors_local_bell_outcomes() -> None:
    """run_descriptors produces correct Bell-state outcomes."""
    descriptors = [
        {"gate": "h", "targets": [0], "controls": [], "params": {}},
        {"gate": "cx", "targets": [1], "controls": [0], "params": {}},
    ]
    result = run_descriptors(descriptors, shots=200)
    unexpected = set(result.counts.keys()) - {"00", "11"}
    assert not unexpected, f"Unexpected outcomes: {unexpected}"


def test_run_descriptors_default_backend_is_local() -> None:
    """run_descriptors defaults to local backend (no AWS needed)."""
    descriptors = [
        {"gate": "x", "targets": [0], "controls": [], "params": {}},
    ]
    result = run_descriptors(descriptors, shots=50)
    assert result.counts.get("1", 0) == 50


def test_run_descriptors_device_missing_arn_raises() -> None:
    """run_descriptors raises ValueError if device_arn is missing for device backend."""
    descriptors = [{"gate": "h", "targets": [0], "controls": [], "params": {}}]
    with pytest.raises(ValueError, match="device_arn"):
        run_descriptors(descriptors, backend="device", s3_folder=("bucket", "prefix"))


def test_run_descriptors_device_missing_s3_raises() -> None:
    """run_descriptors raises ValueError if s3_folder is missing for device backend."""
    descriptors = [{"gate": "h", "targets": [0], "controls": [], "params": {}}]
    with pytest.raises(ValueError, match="s3_folder"):
        run_descriptors(
            descriptors,
            backend="device",
            device_arn="arn:aws:braket:::device/quantum-simulator/amazon/sv1",
        )


def test_run_descriptors_unknown_backend_raises() -> None:
    """run_descriptors raises ValueError for unknown backend."""
    descriptors = [{"gate": "h", "targets": [0], "controls": [], "params": {}}]
    with pytest.raises(ValueError, match="unknown backend"):
        run_descriptors(descriptors, backend="cloud")  # type: ignore[arg-type]


def test_run_descriptors_device_backend_mocked() -> None:
    """run_descriptors with backend='device' calls AwsDevice.run."""
    mock_result = MagicMock()
    mock_result.measurement_counts = Counter({"00": 60, "11": 40})
    mock_result.measurement_probabilities = None
    mock_result.task_metadata = None

    mock_task = MagicMock()
    mock_task.result.return_value = mock_result

    mock_device_instance = MagicMock()
    mock_device_instance.run.return_value = mock_task

    mock_aws = MagicMock()
    mock_aws.AwsDevice = MagicMock(return_value=mock_device_instance)

    descriptors = [
        {"gate": "h", "targets": [0], "controls": [], "params": {}},
        {"gate": "cx", "targets": [1], "controls": [0], "params": {}},
    ]

    with patch.dict("sys.modules", {"braket.aws": mock_aws}):
        result = run_descriptors(
            descriptors,
            shots=100,
            backend="device",
            device_arn="arn:aws:braket:::device/quantum-simulator/amazon/sv1",
            s3_folder=("bucket", "prefix"),
        )

    assert isinstance(result, BraketResult)


# ---------------------------------------------------------------------------
# BraketResult.to_dict() — optional extras
# ---------------------------------------------------------------------------


def test_to_dict_default_keys() -> None:
    """to_dict() with defaults returns only base keys."""
    raw = _make_raw()
    result = BraketResult(raw)
    d = result.to_dict()
    assert "counts" in d
    assert "shots" in d
    assert "backend" in d
    assert "metadata" in d
    assert "probabilities" not in d
    assert "task_id" not in d
    assert "status" not in d


def test_to_dict_include_probabilities() -> None:
    """to_dict(include_probabilities=True) adds 'probabilities' key."""
    raw = _make_raw({"00": 70, "11": 30})
    result = BraketResult(raw)
    d = result.to_dict(include_probabilities=True)
    assert "probabilities" in d
    assert abs(d["probabilities"]["00"] - 0.7) < 1e-9
    assert abs(d["probabilities"]["11"] - 0.3) < 1e-9


def test_to_dict_include_task_id() -> None:
    """to_dict(include_task_id=True) adds 'task_id' key."""
    raw = _make_raw()
    result = BraketResult(raw)
    d = result.to_dict(include_task_id=True)
    assert "task_id" in d


def test_to_dict_include_status() -> None:
    """to_dict(include_status=True) adds 'status' key."""
    raw = _make_raw()
    result = BraketResult(raw)
    d = result.to_dict(include_status=True)
    assert "status" in d


def test_to_dict_all_extras() -> None:
    """to_dict with all flags returns all expected keys."""
    raw = _make_raw()
    result = BraketResult(raw)
    d = result.to_dict(
        include_probabilities=True,
        include_task_id=True,
        include_status=True,
    )
    assert "counts" in d
    assert "shots" in d
    assert "backend" in d
    assert "metadata" in d
    assert "probabilities" in d
    assert "task_id" in d
    assert "status" in d


def test_to_dict_task_id_from_metadata() -> None:
    """to_dict extracts task_id from metadata when available."""
    meta = MagicMock()
    meta.dict.return_value = {"taskId": "arn:aws:braket:us-east-1:123:task/abc", "shots": 100}
    raw = _make_raw(task_metadata=meta)
    result = BraketResult(raw)
    d = result.to_dict(include_task_id=True)
    assert d["task_id"] == "arn:aws:braket:us-east-1:123:task/abc"


def test_to_dict_backend_always_braket() -> None:
    """to_dict always sets 'backend' to 'braket'."""
    raw = _make_raw()
    result = BraketResult(raw)
    d = result.to_dict()
    assert d["backend"] == "braket"


# ---------------------------------------------------------------------------
# BraketBackend — new methods
# ---------------------------------------------------------------------------


def test_backend_run_device_async_returns_arn() -> None:
    """BraketBackend.run_device_async returns a task ARN string."""
    mock_aws, mock_task = _make_mock_aws({"00": 60, "11": 40})
    backend = BraketBackend()
    with patch.dict("sys.modules", {"braket.aws": mock_aws}):
        task_arn = backend.run_device_async(
            bell_circuit(),
            device_arn="arn:aws:braket:::device/quantum-simulator/amazon/sv1",
            s3_folder=("bucket", "prefix"),
            shots=100,
        )
    assert isinstance(task_arn, str)
    assert task_arn == mock_task.id


def test_backend_run_descriptors_local() -> None:
    """BraketBackend.run_descriptors runs a descriptor list locally."""
    backend = BraketBackend()
    descriptors = [
        {"gate": "h", "targets": [0], "controls": [], "params": {}},
        {"gate": "cx", "targets": [1], "controls": [0], "params": {}},
    ]
    result = backend.run_descriptors(descriptors, shots=200)
    assert isinstance(result, BraketResult)
    assert result.shots == 200
    unexpected = set(result.counts.keys()) - {"00", "11"}
    assert not unexpected


def test_backend_run_descriptors_x_gate() -> None:
    """BraketBackend.run_descriptors correctly executes X gate."""
    backend = BraketBackend()
    descriptors = [{"gate": "x", "targets": [0], "controls": [], "params": {}}]
    result = backend.run_descriptors(descriptors, shots=50)
    assert result.counts.get("1", 0) == 50


# ---------------------------------------------------------------------------
# Public API exports
# ---------------------------------------------------------------------------


def test_new_symbols_in_all() -> None:
    """New public symbols must be listed in rqm_braket.__all__."""
    import rqm_braket

    new_symbols = [
        "run_device_async",
        "get_task_status",
        "get_task_result",
        "list_devices",
        "run_descriptors",
        "BraketDeviceError",
    ]
    for sym in new_symbols:
        assert sym in rqm_braket.__all__, f"rqm_braket.__all__ missing '{sym}'"


def test_new_symbols_accessible_from_top_level() -> None:
    """New symbols must be accessible from the top-level rqm_braket package."""
    import rqm_braket

    assert callable(rqm_braket.run_device_async)
    assert callable(rqm_braket.get_task_status)
    assert callable(rqm_braket.get_task_result)
    assert callable(rqm_braket.list_devices)
    assert callable(rqm_braket.run_descriptors)
    assert rqm_braket.BraketDeviceError is not None
