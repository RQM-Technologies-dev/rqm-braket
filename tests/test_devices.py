"""Tests for rqm_braket.devices."""

from unittest.mock import MagicMock, patch

import pytest
from braket.circuits import Circuit

from rqm_braket.circuits import bell_circuit, ghz_circuit, single_qubit_demo_circuit
from rqm_braket.devices import run_local
from rqm_braket.results import BraketResult


# ---------------------------------------------------------------------------
# Local simulator — live (offline-safe)
# ---------------------------------------------------------------------------


def test_run_local_returns_braket_result() -> None:
    """run_local must return a BraketResult."""
    result = run_local(bell_circuit(), shots=50)
    assert isinstance(result, BraketResult)


def test_run_local_shot_count() -> None:
    """Total counts must equal the requested shot count."""
    shots = 80
    result = run_local(bell_circuit(), shots=shots)
    assert result.shots == shots


def test_run_local_bell_state_outcomes() -> None:
    """A Bell circuit should only produce '00' and '11' outcomes."""
    result = run_local(bell_circuit(), shots=200)
    unexpected = set(result.counts.keys()) - {"00", "11"}
    assert not unexpected, f"Unexpected Bell outcomes: {unexpected}"


def test_run_local_single_qubit() -> None:
    """A single-qubit circuit runs without error."""
    result = run_local(single_qubit_demo_circuit(), shots=50)
    assert result.shots == 50
    # Only '0' or '1' outcomes expected
    unexpected = set(result.counts.keys()) - {"0", "1"}
    assert not unexpected


def test_run_local_ghz_outcomes() -> None:
    """A 3-qubit GHZ circuit should only produce '000' and '111' outcomes."""
    result = run_local(ghz_circuit(3), shots=200)
    unexpected = set(result.counts.keys()) - {"000", "111"}
    assert not unexpected, f"Unexpected GHZ outcomes: {unexpected}"


def test_run_local_probabilities_sum_to_one() -> None:
    result = run_local(bell_circuit(), shots=100)
    total = sum(result.probabilities.values())
    assert abs(total - 1.0) < 1e-9


def test_run_local_default_shots() -> None:
    """Default shot count (100) is accepted without error."""
    result = run_local(bell_circuit())
    assert result.shots == 100


# ---------------------------------------------------------------------------
# Circuit helpers
# ---------------------------------------------------------------------------


def test_bell_circuit_structure() -> None:
    """bell_circuit() produces a 2-qubit Braket circuit."""
    circuit = bell_circuit()
    assert isinstance(circuit, Circuit)
    assert circuit.qubit_count == 2


def test_ghz_circuit_structure() -> None:
    """ghz_circuit(n) produces an n-qubit Braket circuit."""
    circuit = ghz_circuit(4)
    assert isinstance(circuit, Circuit)
    assert circuit.qubit_count == 4


def test_ghz_circuit_minimum() -> None:
    """ghz_circuit(2) should work correctly."""
    circuit = ghz_circuit(2)
    assert circuit.qubit_count == 2


def test_ghz_circuit_too_few_qubits() -> None:
    """ghz_circuit requires at least 2 qubits."""
    with pytest.raises(ValueError):
        ghz_circuit(1)


def test_single_qubit_demo_circuit_structure() -> None:
    circuit = single_qubit_demo_circuit()
    assert isinstance(circuit, Circuit)
    assert circuit.qubit_count == 1


# ---------------------------------------------------------------------------
# Cloud execution — mocked (no AWS credentials needed)
# ---------------------------------------------------------------------------


def test_run_device_calls_aws_device() -> None:
    """run_device must call AwsDevice.run and wrap the result."""
    from collections import Counter
    from unittest.mock import MagicMock, patch

    # Build a mock task / result
    mock_counts = Counter({"00": 60, "11": 40})
    mock_result = MagicMock()
    mock_result.measurement_counts = mock_counts
    mock_result.measurement_probabilities = None
    mock_result.task_metadata = None

    mock_task = MagicMock()
    mock_task.result.return_value = mock_result

    mock_device_instance = MagicMock()
    mock_device_instance.run.return_value = mock_task

    MockAwsDevice = MagicMock(return_value=mock_device_instance)

    mock_braket_aws = MagicMock()
    mock_braket_aws.AwsDevice = MockAwsDevice

    with patch.dict("sys.modules", {"braket.aws": mock_braket_aws}):
        from rqm_braket.devices import run_device

        result = run_device(
            bell_circuit(),
            device_arn="arn:aws:braket:::device/quantum-simulator/amazon/sv1",
            s3_folder=("bucket", "prefix"),
            shots=100,
        )

    assert isinstance(result, BraketResult)
