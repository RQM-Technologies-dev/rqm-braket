"""Tests for rqm_braket.backend — BraketBackend."""

from collections import Counter
from unittest.mock import MagicMock, patch

import pytest
from braket.circuits import Circuit

from rqm_braket.backend import BraketBackend
from rqm_braket.circuits import bell_circuit
from rqm_braket.results import BraketResult
from rqm_braket.translator import RQMGate


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def backend() -> BraketBackend:
    return BraketBackend()


# ---------------------------------------------------------------------------
# compile_to_circuit
# ---------------------------------------------------------------------------


def test_compile_to_circuit_returns_circuit(backend: BraketBackend) -> None:
    """compile_to_circuit returns a Braket Circuit."""
    seq = [RQMGate(gate="H", target=0)]
    result = backend.compile_to_circuit(seq)
    assert isinstance(result, Circuit)


def test_compile_to_circuit_bell(backend: BraketBackend) -> None:
    """compile_to_circuit produces the correct 2-qubit Bell circuit."""
    seq = [
        RQMGate(gate="H", target=0),
        RQMGate(gate="CNOT", target=1, control=0),
    ]
    circuit = backend.compile_to_circuit(seq)
    assert circuit.qubit_count == 2


def test_compile_to_circuit_accepts_compiled_program(backend: BraketBackend) -> None:
    """compile_to_circuit accepts a CompiledProgram-like object."""

    class _FakeProgram:
        instructions = [RQMGate(gate="X", target=0)]

    circuit = backend.compile_to_circuit(_FakeProgram())
    assert isinstance(circuit, Circuit)
    assert circuit.qubit_count == 1


# ---------------------------------------------------------------------------
# run_local — via BraketBackend
# ---------------------------------------------------------------------------


def test_backend_run_local_with_circuit(backend: BraketBackend) -> None:
    """BraketBackend.run_local works with a pre-built Circuit."""
    result = backend.run_local(bell_circuit(), shots=100)
    assert isinstance(result, BraketResult)
    assert result.shots == 100


def test_backend_run_local_with_rqmgate_sequence(backend: BraketBackend) -> None:
    """BraketBackend.run_local accepts a RQMGate sequence."""
    seq = [RQMGate(gate="X", target=0)]
    result = backend.run_local(seq, shots=50)
    assert isinstance(result, BraketResult)
    assert result.counts.get("1", 0) == 50


def test_backend_run_local_default_shots(backend: BraketBackend) -> None:
    """BraketBackend.run_local uses 100 shots by default."""
    result = backend.run_local(bell_circuit())
    assert result.shots == 100


def test_backend_run_local_bell_outcomes(backend: BraketBackend) -> None:
    """Bell state via BraketBackend produces only '00' and '11'."""
    seq = [
        RQMGate(gate="H", target=0),
        RQMGate(gate="CNOT", target=1, control=0),
    ]
    result = backend.run_local(seq, shots=200)
    unexpected = set(result.counts.keys()) - {"00", "11"}
    assert not unexpected


def test_compile_run_identity() -> None:
    """End-to-end: compile a Bell program, run locally, verify both outcomes."""
    program = [
        RQMGate("H", target=0),
        RQMGate("CNOT", control=0, target=1),
    ]

    backend = BraketBackend()
    result = backend.run_local(program, shots=200)

    assert "00" in result.counts
    assert "11" in result.counts


# ---------------------------------------------------------------------------
# run_device — mocked (no AWS credentials needed)
# ---------------------------------------------------------------------------


def _make_mock_aws(counts: dict[str, int]) -> tuple[MagicMock, MagicMock]:
    """Return (mock_braket_aws_module, mock_device_instance)."""
    mock_result = MagicMock()
    mock_result.measurement_counts = Counter(counts)
    mock_result.measurement_probabilities = None
    mock_result.task_metadata = None

    mock_task = MagicMock()
    mock_task.result.return_value = mock_result

    mock_device_instance = MagicMock()
    mock_device_instance.run.return_value = mock_task

    mock_aws_module = MagicMock()
    mock_aws_module.AwsDevice = MagicMock(return_value=mock_device_instance)

    return mock_aws_module, mock_device_instance


def test_backend_run_device_with_circuit(backend: BraketBackend) -> None:
    """BraketBackend.run_device calls AwsDevice.run and wraps the result."""
    mock_aws, _ = _make_mock_aws({"00": 60, "11": 40})
    with patch.dict("sys.modules", {"braket.aws": mock_aws}):
        result = backend.run_device(
            bell_circuit(),
            device_arn="arn:aws:braket:::device/quantum-simulator/amazon/sv1",
            s3_folder=("bucket", "prefix"),
            shots=100,
        )
    assert isinstance(result, BraketResult)


def test_backend_run_device_translates_rqmgate(backend: BraketBackend) -> None:
    """BraketBackend.run_device passes a Circuit (not raw list) to AwsDevice."""
    mock_aws, mock_device = _make_mock_aws({"1": 50})
    with patch.dict("sys.modules", {"braket.aws": mock_aws}):
        backend.run_device(
            [RQMGate(gate="X", target=0)],
            device_arn="arn:aws:braket:::device/quantum-simulator/amazon/sv1",
            s3_folder=("bucket", "prefix"),
            shots=50,
        )
    call_args = mock_device.run.call_args
    assert isinstance(call_args[0][0], Circuit)
