"""
Tests for new rqm-API functionality added in the rqm-API update.

Covers:
- translate_descriptors (canonical descriptor format)
- u1q gate (quaternion → SU(2) → Braket Unitary)
- measure gate
- barrier gate (no-op)
- to_backend_circuit (rqm-compiler integration)
- BraketResult.to_dict() (API-ready output)
- BraketBackend.compile() / BraketBackend.run() methods
- types module
"""

from __future__ import annotations

import math
from collections import Counter
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from braket.circuits import Circuit

import rqm_braket
from rqm_braket.backend import BraketBackend
from rqm_braket.results import BraketResult
from rqm_braket.translator import (
    BraketTranslator,
    RQMGate,
    to_backend_circuit,
)
from rqm_braket.types import Descriptor, DescriptorList


# ---------------------------------------------------------------------------
# types module
# ---------------------------------------------------------------------------


def test_descriptor_type_alias() -> None:
    """Descriptor is a plain dict type alias."""
    op: Descriptor = {"gate": "h", "targets": [0], "controls": [], "params": {}}
    assert isinstance(op, dict)


def test_descriptor_list_type_alias() -> None:
    """DescriptorList is a list of dicts."""
    ops: DescriptorList = [
        {"gate": "h", "targets": [0], "controls": [], "params": {}},
    ]
    assert isinstance(ops, list)


# ---------------------------------------------------------------------------
# translate_descriptors — canonical descriptor format
# ---------------------------------------------------------------------------


def test_translate_descriptors_single_qubit() -> None:
    """translate_descriptors handles single-qubit gates from descriptor dicts."""
    translator = BraketTranslator()
    descriptors: DescriptorList = [
        {"gate": "h", "targets": [0], "controls": [], "params": {}},
    ]
    circuit = translator.translate_descriptors(descriptors)
    assert isinstance(circuit, Circuit)
    assert circuit.qubit_count == 1


def test_translate_descriptors_bell_state() -> None:
    """translate_descriptors builds a Bell-state circuit from descriptors."""
    translator = BraketTranslator()
    descriptors: DescriptorList = [
        {"gate": "h", "targets": [0], "controls": [], "params": {}},
        {"gate": "cx", "targets": [1], "controls": [0], "params": {}},
    ]
    circuit = translator.translate_descriptors(descriptors)
    assert circuit.qubit_count == 2


def test_translate_descriptors_rotation_gate() -> None:
    """translate_descriptors handles rotation gates with params dict."""
    translator = BraketTranslator()
    descriptors: DescriptorList = [
        {"gate": "rx", "targets": [0], "controls": [], "params": {"angle": math.pi / 2}},
    ]
    circuit = translator.translate_descriptors(descriptors)
    assert circuit.qubit_count == 1


@pytest.mark.parametrize("gate", ["h", "x", "y", "z", "s", "t", "i"])
def test_translate_descriptors_all_single_qubit_gates(gate: str) -> None:
    """All canonical single-qubit gates translate via descriptor format."""
    translator = BraketTranslator()
    circuit = translator.translate_descriptors([
        {"gate": gate, "targets": [0], "controls": [], "params": {}},
    ])
    assert isinstance(circuit, Circuit)
    assert circuit.qubit_count == 1


@pytest.mark.parametrize(
    "gate,params",
    [
        ("rx", {"angle": math.pi / 4}),
        ("ry", {"angle": math.pi / 2}),
        ("rz", {"angle": math.pi}),
        ("phaseshift", {"angle": math.pi / 3}),
    ],
)
def test_translate_descriptors_rotation_gates(gate: str, params: dict) -> None:
    """All canonical rotation gates translate via descriptor format."""
    translator = BraketTranslator()
    circuit = translator.translate_descriptors([
        {"gate": gate, "targets": [0], "controls": [], "params": params},
    ])
    assert circuit.qubit_count == 1


@pytest.mark.parametrize("gate", ["cx", "cy", "cz", "swap", "iswap"])
def test_translate_descriptors_two_qubit_gates(gate: str) -> None:
    """All canonical two-qubit gates translate via descriptor format."""
    translator = BraketTranslator()
    circuit = translator.translate_descriptors([
        {"gate": gate, "targets": [1], "controls": [0], "params": {}},
    ])
    assert circuit.qubit_count == 2


def test_translate_descriptors_upper_case_gate_name() -> None:
    """Gate names in descriptor format are case-insensitive."""
    translator = BraketTranslator()
    circuit = translator.translate_descriptors([
        {"gate": "H", "targets": [0], "controls": [], "params": {}},
    ])
    assert circuit.qubit_count == 1


def test_translate_descriptors_unknown_gate_raises() -> None:
    """An unknown gate name in descriptor format raises ValueError."""
    translator = BraketTranslator()
    with pytest.raises(ValueError, match="Unknown gate"):
        translator.translate_descriptors([
            {"gate": "MAGIC", "targets": [0], "controls": [], "params": {}},
        ])


def test_translate_descriptors_empty_list() -> None:
    """An empty descriptor list yields an empty circuit."""
    translator = BraketTranslator()
    circuit = translator.translate_descriptors([])
    assert isinstance(circuit, Circuit)
    assert circuit.qubit_count == 0


# ---------------------------------------------------------------------------
# measure gate
# ---------------------------------------------------------------------------


def test_measure_gate_via_rqmgate() -> None:
    """MEASURE gate via RQMGate appends a measurement to the circuit."""
    translator = BraketTranslator()
    circuit = translator.to_circuit([
        RQMGate(gate="H", target=0),
        RQMGate(gate="MEASURE", target=0),
    ])
    assert isinstance(circuit, Circuit)
    assert circuit.qubit_count == 1


def test_measure_gate_via_descriptor() -> None:
    """measure gate via descriptor format appends a measurement."""
    translator = BraketTranslator()
    circuit = translator.translate_descriptors([
        {"gate": "h", "targets": [0], "controls": [], "params": {}},
        {"gate": "measure", "targets": [0], "controls": [], "params": {}},
    ])
    assert isinstance(circuit, Circuit)
    assert circuit.qubit_count == 1


# ---------------------------------------------------------------------------
# barrier gate (no-op)
# ---------------------------------------------------------------------------


def test_barrier_gate_via_rqmgate_is_noop() -> None:
    """BARRIER gate via RQMGate is a no-op; circuit is unchanged."""
    translator = BraketTranslator()
    circuit_without = translator.to_circuit([RQMGate(gate="H", target=0)])
    circuit_with = translator.to_circuit([
        RQMGate(gate="H", target=0),
        RQMGate(gate="BARRIER", target=0),
    ])
    assert len(circuit_without.instructions) == len(circuit_with.instructions)


def test_barrier_gate_via_descriptor_is_noop() -> None:
    """barrier descriptor is treated as a no-op."""
    translator = BraketTranslator()
    circuit = translator.translate_descriptors([
        {"gate": "h", "targets": [0], "controls": [], "params": {}},
        {"gate": "barrier", "targets": [0], "controls": [], "params": {}},
    ])
    # Only the H gate instruction should appear
    assert len(circuit.instructions) == 1


# ---------------------------------------------------------------------------
# u1q gate (quaternion → SU(2) unitary)
# ---------------------------------------------------------------------------


def test_u1q_identity_quaternion_via_descriptor() -> None:
    """u1q with identity quaternion (w=1, xyz=0) acts as identity."""
    translator = BraketTranslator()
    circuit = translator.translate_descriptors([
        {"gate": "u1q", "targets": [0], "controls": [], "params": {
            "w": 1.0, "x": 0.0, "y": 0.0, "z": 0.0,
        }},
    ])
    assert isinstance(circuit, Circuit)
    assert circuit.qubit_count == 1


def test_u1q_x_rotation_via_descriptor() -> None:
    """u1q with π rotation around X axis corresponds to X gate."""
    translator = BraketTranslator()
    circuit = translator.translate_descriptors([
        {"gate": "u1q", "targets": [0], "controls": [], "params": {
            "w": 0.0, "x": 1.0, "y": 0.0, "z": 0.0,
        }},
    ])
    assert circuit.qubit_count == 1


def test_u1q_arbitrary_quaternion_via_descriptor() -> None:
    """u1q with an arbitrary normalised quaternion produces a valid circuit."""
    # 60° rotation around Z: q = (cos 30°, 0, 0, sin 30°)
    half = math.pi / 6  # 30°
    w, z = math.cos(half), math.sin(half)
    translator = BraketTranslator()
    circuit = translator.translate_descriptors([
        {"gate": "u1q", "targets": [0], "controls": [], "params": {
            "w": w, "x": 0.0, "y": 0.0, "z": z,
        }},
    ])
    assert circuit.qubit_count == 1


def test_u1q_via_rqmgate_with_params() -> None:
    """u1q via RQMGate with params dict works correctly."""
    translator = BraketTranslator()

    class _U1QGate:
        gate = "U1Q"
        target = 0
        control = None
        angle = None
        params = {"w": 1.0, "x": 0.0, "y": 0.0, "z": 0.0}

    circuit = translator.to_circuit([_U1QGate()])
    assert isinstance(circuit, Circuit)
    assert circuit.qubit_count == 1


def test_u1q_missing_params_raises() -> None:
    """u1q without params raises ValueError."""
    translator = BraketTranslator()
    with pytest.raises(ValueError, match="U1Q"):
        translator.to_circuit([RQMGate(gate="U1Q", target=0)])


def test_u1q_matrix_is_unitary() -> None:
    """The SU(2) matrix produced for a u1q gate is unitary."""
    from rqm_core import Quaternion

    # Test with a non-trivial quaternion: 90° rotation around Y
    half = math.pi / 4  # 45°
    q = Quaternion(math.cos(half), 0.0, math.sin(half), 0.0)
    matrix = np.array(q.to_su2_matrix(), dtype=complex)
    product = matrix @ matrix.conj().T
    assert np.allclose(product, np.eye(2), atol=1e-10)


# ---------------------------------------------------------------------------
# to_backend_circuit — rqm-compiler integration
# ---------------------------------------------------------------------------


def test_to_backend_circuit_raises_import_error_without_compiler() -> None:
    """to_backend_circuit raises ImportError if rqm-compiler is not installed."""
    with patch.dict("sys.modules", {"rqm_compiler": None}):
        with pytest.raises(ImportError, match="rqm-compiler"):
            to_backend_circuit(MagicMock())


def test_to_backend_circuit_calls_compile_circuit() -> None:
    """to_backend_circuit calls compile_circuit and translates descriptors."""
    mock_descriptors = [
        {"gate": "h", "targets": [0], "controls": [], "params": {}},
        {"gate": "cx", "targets": [1], "controls": [0], "params": {}},
    ]

    mock_compiled_circuit = MagicMock()
    mock_compiled_circuit.to_descriptors.return_value = mock_descriptors

    mock_compiled_program = MagicMock()
    mock_compiled_program.circuit = mock_compiled_circuit

    mock_compile_circuit = MagicMock(return_value=mock_compiled_program)
    mock_optimize_circuit = MagicMock()

    mock_rqm_compiler = MagicMock()
    mock_rqm_compiler.compile_circuit = mock_compile_circuit
    mock_rqm_compiler.optimize_circuit = mock_optimize_circuit

    with patch.dict("sys.modules", {"rqm_compiler": mock_rqm_compiler}):
        circuit = to_backend_circuit(MagicMock())

    assert isinstance(circuit, Circuit)
    assert circuit.qubit_count == 2
    mock_compile_circuit.assert_called_once()
    mock_optimize_circuit.assert_not_called()


def test_to_backend_circuit_calls_optimize_circuit_when_optimize_true() -> None:
    """to_backend_circuit calls optimize_circuit when optimize=True."""
    mock_descriptors = [
        {"gate": "x", "targets": [0], "controls": [], "params": {}},
    ]

    mock_optimized_circuit = MagicMock()
    mock_optimized_circuit.to_descriptors.return_value = mock_descriptors

    mock_optimize_circuit = MagicMock(return_value=(mock_optimized_circuit, MagicMock()))
    mock_compile_circuit = MagicMock()

    mock_rqm_compiler = MagicMock()
    mock_rqm_compiler.compile_circuit = mock_compile_circuit
    mock_rqm_compiler.optimize_circuit = mock_optimize_circuit

    with patch.dict("sys.modules", {"rqm_compiler": mock_rqm_compiler}):
        circuit = to_backend_circuit(MagicMock(), optimize=True)

    assert isinstance(circuit, Circuit)
    mock_optimize_circuit.assert_called_once()
    mock_compile_circuit.assert_not_called()


def test_to_backend_circuit_accessible_from_top_level() -> None:
    """to_backend_circuit is exported from the top-level rqm_braket package."""
    assert callable(rqm_braket.to_backend_circuit)


def test_to_backend_circuit_in_all() -> None:
    """to_backend_circuit is listed in rqm_braket.__all__."""
    assert "to_backend_circuit" in rqm_braket.__all__


# ---------------------------------------------------------------------------
# BraketResult.to_dict()
# ---------------------------------------------------------------------------


def _make_raw_result(counts: dict[str, int]) -> MagicMock:
    raw = MagicMock()
    raw.measurement_counts = Counter(counts)
    raw.measurement_probabilities = None
    raw.task_metadata = None
    return raw


def test_to_dict_returns_dict() -> None:
    """to_dict returns a plain dict."""
    result = BraketResult(_make_raw_result({"00": 60, "11": 40}))
    d = result.to_dict()
    assert isinstance(d, dict)


def test_to_dict_has_required_keys() -> None:
    """to_dict contains 'counts', 'shots', 'backend', and 'metadata' keys."""
    result = BraketResult(_make_raw_result({"00": 60, "11": 40}))
    d = result.to_dict()
    assert "counts" in d
    assert "shots" in d
    assert "backend" in d
    assert "metadata" in d


def test_to_dict_counts_is_plain_dict() -> None:
    """to_dict['counts'] is a plain dict, not a Counter."""
    result = BraketResult(_make_raw_result({"00": 60, "11": 40}))
    d = result.to_dict()
    assert type(d["counts"]) is dict
    assert d["counts"]["00"] == 60
    assert d["counts"]["11"] == 40


def test_to_dict_shots_correct() -> None:
    """to_dict['shots'] equals the total number of shots."""
    result = BraketResult(_make_raw_result({"00": 70, "11": 30}))
    d = result.to_dict()
    assert d["shots"] == 100


def test_to_dict_backend_is_braket() -> None:
    """to_dict['backend'] is always 'braket'."""
    result = BraketResult(_make_raw_result({"0": 100}))
    assert result.to_dict()["backend"] == "braket"


def test_to_dict_metadata_is_dict() -> None:
    """to_dict['metadata'] is a plain dict."""
    result = BraketResult(_make_raw_result({"0": 100}))
    assert isinstance(result.to_dict()["metadata"], dict)


def test_to_dict_is_json_serializable() -> None:
    """to_dict output is JSON-serializable."""
    import json

    result = BraketResult(_make_raw_result({"00": 55, "11": 45}))
    d = result.to_dict()
    serialized = json.dumps(d)
    recovered = json.loads(serialized)
    assert recovered["shots"] == 100
    assert recovered["backend"] == "braket"


def test_to_dict_via_run_local() -> None:
    """to_dict works on a real BraketResult from run_local."""
    from rqm_braket.circuits import bell_circuit
    from rqm_braket.execution import run_local

    result = run_local(bell_circuit(), shots=100)
    d = result.to_dict()
    assert d["shots"] == 100
    assert d["backend"] == "braket"
    assert isinstance(d["counts"], dict)
    assert isinstance(d["metadata"], dict)


# ---------------------------------------------------------------------------
# BraketBackend.compile() and BraketBackend.run()
# ---------------------------------------------------------------------------


def test_backend_compile_raises_import_error_without_compiler() -> None:
    """BraketBackend.compile raises ImportError if rqm-compiler is missing."""
    backend = BraketBackend()
    with patch.dict("sys.modules", {"rqm_compiler": None}):
        with pytest.raises(ImportError, match="rqm-compiler"):
            backend.compile(MagicMock())


def test_backend_compile_calls_to_backend_circuit() -> None:
    """BraketBackend.compile delegates to to_backend_circuit."""
    mock_descriptors: DescriptorList = [
        {"gate": "x", "targets": [0], "controls": [], "params": {}},
    ]
    mock_circuit = MagicMock()
    mock_circuit.to_descriptors.return_value = mock_descriptors

    mock_compiled = MagicMock()
    mock_compiled.circuit = mock_circuit

    mock_rqm_compiler = MagicMock()
    mock_rqm_compiler.compile_circuit = MagicMock(return_value=mock_compiled)
    mock_rqm_compiler.optimize_circuit = MagicMock()

    backend = BraketBackend()
    with patch.dict("sys.modules", {"rqm_compiler": mock_rqm_compiler}):
        circuit = backend.compile(MagicMock())

    assert isinstance(circuit, Circuit)


def test_backend_run_raises_import_error_without_compiler() -> None:
    """BraketBackend.run raises ImportError if rqm-compiler is missing."""
    backend = BraketBackend()
    with patch.dict("sys.modules", {"rqm_compiler": None}):
        with pytest.raises(ImportError, match="rqm-compiler"):
            backend.run(MagicMock())


def test_backend_run_returns_braket_result() -> None:
    """BraketBackend.run compiles and executes, returning a BraketResult."""
    mock_descriptors: DescriptorList = [
        {"gate": "h", "targets": [0], "controls": [], "params": {}},
        {"gate": "cx", "targets": [1], "controls": [0], "params": {}},
    ]
    mock_circuit = MagicMock()
    mock_circuit.to_descriptors.return_value = mock_descriptors

    mock_compiled = MagicMock()
    mock_compiled.circuit = mock_circuit

    mock_rqm_compiler = MagicMock()
    mock_rqm_compiler.compile_circuit = MagicMock(return_value=mock_compiled)
    mock_rqm_compiler.optimize_circuit = MagicMock()

    backend = BraketBackend()
    with patch.dict("sys.modules", {"rqm_compiler": mock_rqm_compiler}):
        result = backend.run(MagicMock(), shots=200)

    assert isinstance(result, BraketResult)
    assert result.shots == 200


def test_backend_run_to_dict_integration() -> None:
    """BraketBackend.run result supports to_dict()."""
    mock_descriptors: DescriptorList = [
        {"gate": "x", "targets": [0], "controls": [], "params": {}},
    ]
    mock_circuit = MagicMock()
    mock_circuit.to_descriptors.return_value = mock_descriptors

    mock_compiled = MagicMock()
    mock_compiled.circuit = mock_circuit

    mock_rqm_compiler = MagicMock()
    mock_rqm_compiler.compile_circuit = MagicMock(return_value=mock_compiled)
    mock_rqm_compiler.optimize_circuit = MagicMock()

    backend = BraketBackend()
    with patch.dict("sys.modules", {"rqm_compiler": mock_rqm_compiler}):
        result = backend.run(MagicMock(), shots=100)

    d = result.to_dict()
    assert d["backend"] == "braket"
    assert d["shots"] == 100
    assert isinstance(d["counts"], dict)
