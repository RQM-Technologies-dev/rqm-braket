"""Tests for rqm_braket.execution — run_local and run_device."""

from collections import Counter
from unittest.mock import MagicMock, patch

import pytest
from braket.circuits import Circuit

from rqm_braket.circuits import bell_circuit, ghz_circuit
from rqm_braket.execution import run_local
from rqm_braket.results import BraketResult
from rqm_braket.translator import RQMGate


# ---------------------------------------------------------------------------
# run_local — accepting a plain Circuit
# ---------------------------------------------------------------------------


def test_run_local_circuit_returns_braket_result() -> None:
    """run_local(Circuit) must return a BraketResult."""
    result = run_local(bell_circuit(), shots=50)
    assert isinstance(result, BraketResult)


def test_run_local_circuit_shot_count() -> None:
    """Total counts must equal the requested shot count."""
    result = run_local(bell_circuit(), shots=80)
    assert result.shots == 80


def test_run_local_circuit_bell_outcomes() -> None:
    """Bell circuit produces only '00' and '11' outcomes."""
    result = run_local(bell_circuit(), shots=200)
    unexpected = set(result.counts.keys()) - {"00", "11"}
    assert not unexpected, f"Unexpected outcomes: {unexpected}"


def test_run_local_circuit_default_shots() -> None:
    """Default shot count (100) is accepted."""
    result = run_local(bell_circuit())
    assert result.shots == 100


def test_run_local_circuit_probabilities_sum_to_one() -> None:
    result = run_local(bell_circuit(), shots=100)
    total = sum(result.probabilities.values())
    assert abs(total - 1.0) < 1e-9


def test_run_local_circuit_ghz_outcomes() -> None:
    """3-qubit GHZ circuit produces only '000' and '111'."""
    result = run_local(ghz_circuit(3), shots=200)
    unexpected = set(result.counts.keys()) - {"000", "111"}
    assert not unexpected


# ---------------------------------------------------------------------------
# run_local — accepting a compiled program (RQMGate sequence)
# ---------------------------------------------------------------------------


def test_run_local_rqmgate_sequence() -> None:
    """run_local accepts a list of RQMGate objects and runs them."""
    seq = [
        RQMGate(gate="H", target=0),
        RQMGate(gate="CNOT", target=1, control=0),
    ]
    result = run_local(seq, shots=100)
    assert isinstance(result, BraketResult)
    assert result.shots == 100
    unexpected = set(result.counts.keys()) - {"00", "11"}
    assert not unexpected


def test_run_local_compiled_program_object() -> None:
    """run_local accepts a CompiledProgram-like object."""

    class _FakeProgram:
        instructions = [RQMGate(gate="X", target=0)]

    result = run_local(_FakeProgram(), shots=50)
    assert isinstance(result, BraketResult)
    # X gate on |0⟩ produces |1⟩ deterministically
    assert result.counts.get("1", 0) == 50


# ---------------------------------------------------------------------------
# run_device — mocked (no AWS credentials needed)
# ---------------------------------------------------------------------------


def test_run_device_accepts_circuit() -> None:
    """run_device calls AwsDevice.run and wraps the result."""
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
        from rqm_braket.execution import run_device

        result = run_device(
            bell_circuit(),
            device_arn="arn:aws:braket:::device/quantum-simulator/amazon/sv1",
            s3_folder=("bucket", "prefix"),
            shots=100,
        )

    assert isinstance(result, BraketResult)


def test_run_device_accepts_rqmgate_sequence() -> None:
    """run_device translates an RQMGate sequence before execution."""
    mock_counts = Counter({"0": 100})
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
        from rqm_braket.execution import run_device

        result = run_device(
            [RQMGate(gate="X", target=0)],
            device_arn="arn:aws:braket:::device/quantum-simulator/amazon/sv1",
            s3_folder=("bucket", "prefix"),
            shots=100,
        )

    assert isinstance(result, BraketResult)
    # AwsDevice.run must have been called with a Circuit (not with the raw list)
    call_args = mock_device_instance.run.call_args
    assert isinstance(call_args[0][0], Circuit)
