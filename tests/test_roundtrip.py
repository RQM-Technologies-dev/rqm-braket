"""
Tests for new rqm-API functionality added in the rqm-API update.

Covers:
- translate_descriptors (canonical descriptor format)
- u1q policy boundaries (hardware rejection, local-only compatibility)
- measure gate
- barrier gate (no-op)
- to_backend_circuit (rqm-compiler integration)
- BraketResult.to_dict() (API-ready output)
- BraketBackend.compile() / BraketBackend.run() methods
- types module
- _validate_descriptor() validation layer
"""

from __future__ import annotations

import math
from collections import Counter
from unittest.mock import MagicMock, patch

import pytest
from braket.circuits import Circuit

import rqm_braket
from rqm_braket.backend import BraketBackend
from rqm_braket.execution import run_device, run_local
from rqm_braket.results import BraketResult
from rqm_braket.translator import (
    BraketTranslator,
    RQMGate,
    _validate_descriptor,
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
# u1q policy boundaries
# ---------------------------------------------------------------------------


def test_hardware_translation_rejects_u1q_descriptor_locally() -> None:
    """Default (hardware-oriented) descriptor translation rejects raw u1q."""
    translator = BraketTranslator()
    with pytest.raises(
        ValueError,
        match="U1Q/arbitrary-unitary lowering is not supported",
    ):
        translator.translate_descriptors([
            {"gate": "u1q", "targets": [0], "controls": [], "params": {
                "w": 1.0, "x": 0.0, "y": 0.0, "z": 0.0,
            }},
        ])


def test_hardware_translation_rejects_u1q_rqmgate_locally() -> None:
    """Default (hardware-oriented) attribute-path translation rejects raw u1q."""
    translator = BraketTranslator()

    class _U1QGate:
        gate = "U1Q"
        target = 0
        control = None
        angle = None
        params = {"w": 1.0, "x": 0.0, "y": 0.0, "z": 0.0}

    with pytest.raises(
        ValueError,
        match="U1Q/arbitrary-unitary lowering is not supported",
    ):
        translator.to_circuit([_U1QGate()])


def test_local_only_u1q_compatibility_is_explicit_and_uses_unitary() -> None:
    """Local compatibility mode must be explicit and uses Circuit.unitary."""
    translator = BraketTranslator(allow_local_u1q_unitary=True)
    with patch.object(
        Circuit,
        "unitary",
        autospec=True,
        wraps=Circuit.unitary,
    ) as unitary_mock:
        circuit = translator.translate_descriptors([
            {"gate": "u1q", "targets": [0], "controls": [], "params": {
                "w": 1.0, "x": 0.0, "y": 0.0, "z": 0.0,
            }},
        ])
    assert circuit.qubit_count == 1
    assert unitary_mock.call_count == 1


def test_local_execution_accepts_raw_u1q_via_explicit_local_compatibility() -> None:
    """run_local keeps temporary raw-u1q compatibility for backward compatibility."""
    class _U1QGate:
        gate = "U1Q"
        target = 0
        control = None
        angle = None
        params = {"w": 1.0, "x": 0.0, "y": 0.0, "z": 0.0}

    result = run_local([_U1QGate()], shots=10)
    assert isinstance(result, BraketResult)
    assert result.shots == 10


def test_hardware_oriented_translation_path_does_not_emit_unitary_for_u1q() -> None:
    """Hardware-oriented translation fails before any Circuit.unitary call."""
    translator = BraketTranslator()
    with patch.object(
        Circuit,
        "unitary",
        autospec=True,
        wraps=Circuit.unitary,
    ) as unitary_mock:
        with pytest.raises(
            ValueError,
            match="U1Q/arbitrary-unitary lowering is not supported",
        ):
            translator.translate_descriptors([
                {"gate": "u1q", "targets": [0], "controls": [], "params": {
                    "w": 1.0, "x": 0.0, "y": 0.0, "z": 0.0,
                }},
            ])
    assert unitary_mock.call_count == 0


def test_run_device_rejects_raw_u1q_before_aws_submission() -> None:
    """run_device raises local policy error before creating/running AwsDevice."""
    class _U1QGate:
        gate = "U1Q"
        target = 0
        control = None
        angle = None
        params = {"w": 1.0, "x": 0.0, "y": 0.0, "z": 0.0}

    with patch.dict("sys.modules", {"braket.aws": MagicMock()}):
        with pytest.raises(
            ValueError,
            match="U1Q/arbitrary-unitary lowering is not supported",
        ):
            run_device(
                [_U1QGate()],
                device_arn="arn:aws:braket:::device/qpu/test",
                s3_folder=("bucket", "prefix"),
                shots=1,
            )


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


# ---------------------------------------------------------------------------
# _validate_descriptor — validation layer
# ---------------------------------------------------------------------------


def test_validate_descriptor_valid_single_qubit() -> None:
    """A well-formed single-qubit descriptor passes validation without error."""
    _validate_descriptor({"gate": "h", "targets": [0], "controls": [], "params": {}})


def test_validate_descriptor_valid_rotation() -> None:
    """A well-formed rotation gate descriptor passes validation."""
    _validate_descriptor({"gate": "rx", "targets": [0], "controls": [], "params": {"angle": 1.57}})


def test_validate_descriptor_valid_two_qubit() -> None:
    """A well-formed two-qubit gate descriptor passes validation."""
    _validate_descriptor({"gate": "cx", "targets": [1], "controls": [0], "params": {}})


def test_validate_descriptor_valid_u1q() -> None:
    """A well-formed u1q descriptor with all quaternion params passes validation."""
    _validate_descriptor({
        "gate": "u1q", "targets": [0], "controls": [], "params": {
            "w": 1.0, "x": 0.0, "y": 0.0, "z": 0.0,
        },
    })


def test_validate_descriptor_valid_measure() -> None:
    """A well-formed measure descriptor passes validation."""
    _validate_descriptor({"gate": "measure", "targets": [0], "controls": [], "params": {}})


def test_validate_descriptor_valid_barrier() -> None:
    """A well-formed barrier descriptor passes validation."""
    _validate_descriptor({"gate": "barrier", "targets": [0], "controls": [], "params": {}})


def test_validate_descriptor_not_a_dict_raises_type_error() -> None:
    """A non-dict descriptor raises TypeError."""
    with pytest.raises(TypeError, match="dict"):
        _validate_descriptor("not a dict")  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="dict"):
        _validate_descriptor(["gate", "h"])  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="dict"):
        _validate_descriptor(None)  # type: ignore[arg-type]


def test_validate_descriptor_missing_gate_key_raises() -> None:
    """Missing 'gate' key raises ValueError listing the missing key."""
    with pytest.raises(ValueError, match="gate"):
        _validate_descriptor({"targets": [0], "controls": [], "params": {}})


def test_validate_descriptor_missing_targets_key_raises() -> None:
    """Missing 'targets' key raises ValueError."""
    with pytest.raises(ValueError, match="targets"):
        _validate_descriptor({"gate": "h", "controls": [], "params": {}})


def test_validate_descriptor_missing_controls_key_raises() -> None:
    """Missing 'controls' key raises ValueError."""
    with pytest.raises(ValueError, match="controls"):
        _validate_descriptor({"gate": "h", "targets": [0], "params": {}})


def test_validate_descriptor_missing_params_key_raises() -> None:
    """Missing 'params' key raises ValueError."""
    with pytest.raises(ValueError, match="params"):
        _validate_descriptor({"gate": "h", "targets": [0], "controls": []})


def test_validate_descriptor_multiple_missing_keys_raises() -> None:
    """Multiple missing keys are reported together."""
    with pytest.raises(ValueError, match="missing required keys"):
        _validate_descriptor({})


def test_validate_descriptor_wrong_gate_type_raises() -> None:
    """A non-string 'gate' value raises TypeError."""
    with pytest.raises(TypeError, match="gate.*str"):
        _validate_descriptor({"gate": 42, "targets": [0], "controls": [], "params": {}})


def test_validate_descriptor_wrong_targets_type_raises() -> None:
    """A non-list 'targets' raises TypeError."""
    with pytest.raises(TypeError, match="targets.*list"):
        _validate_descriptor({"gate": "h", "targets": 0, "controls": [], "params": {}})


def test_validate_descriptor_wrong_controls_type_raises() -> None:
    """A non-list 'controls' raises TypeError."""
    with pytest.raises(TypeError, match="controls.*list"):
        _validate_descriptor({"gate": "h", "targets": [0], "controls": 0, "params": {}})


def test_validate_descriptor_wrong_params_type_raises() -> None:
    """A non-dict 'params' raises TypeError."""
    with pytest.raises(TypeError, match="params.*dict"):
        _validate_descriptor({"gate": "h", "targets": [0], "controls": [], "params": "bad"})


def test_validate_descriptor_empty_gate_name_raises() -> None:
    """An empty 'gate' string raises ValueError."""
    with pytest.raises(ValueError, match="empty"):
        _validate_descriptor({"gate": "", "targets": [0], "controls": [], "params": {}})


def test_validate_descriptor_unknown_gate_raises() -> None:
    """An unrecognised gate name raises ValueError."""
    with pytest.raises(ValueError, match="Unknown gate"):
        _validate_descriptor({"gate": "FOOBAR", "targets": [0], "controls": [], "params": {}})


def test_validate_descriptor_rotation_missing_angle_raises() -> None:
    """A rotation gate descriptor without 'angle' in params raises ValueError."""
    with pytest.raises(ValueError, match="angle"):
        _validate_descriptor({"gate": "rx", "targets": [0], "controls": [], "params": {}})


def test_validate_descriptor_rotation_wrong_angle_type_raises() -> None:
    """A rotation gate with a non-numeric 'angle' raises TypeError."""
    with pytest.raises(TypeError, match="angle.*number"):
        _validate_descriptor({
            "gate": "rx", "targets": [0], "controls": [], "params": {"angle": "fast"},
        })


def test_validate_descriptor_u1q_missing_quaternion_key_raises() -> None:
    """u1q descriptor missing any of w/x/y/z raises ValueError."""
    for missing_key in ("w", "x", "y", "z"):
        params = {"w": 1.0, "x": 0.0, "y": 0.0, "z": 0.0}
        del params[missing_key]
        with pytest.raises(ValueError, match=missing_key):
            _validate_descriptor({"gate": "u1q", "targets": [0], "controls": [], "params": params})


def test_validate_descriptor_u1q_wrong_param_type_raises() -> None:
    """u1q descriptor with a non-numeric quaternion component raises TypeError."""
    with pytest.raises(TypeError, match="number"):
        _validate_descriptor({
            "gate": "u1q", "targets": [0], "controls": [], "params": {
                "w": "one", "x": 0.0, "y": 0.0, "z": 0.0,
            },
        })


def test_validate_descriptor_called_by_apply_descriptor() -> None:
    """_apply_descriptor invokes validation; invalid descriptors raise before translation."""
    translator = BraketTranslator()
    with pytest.raises(ValueError, match="missing required keys"):
        translator.translate_descriptors([{"gate": "h"}])  # missing targets/controls/params


def test_validate_descriptor_called_by_translate_descriptors_type_error() -> None:
    """translate_descriptors propagates TypeError from _validate_descriptor."""
    translator = BraketTranslator()
    with pytest.raises(TypeError, match="dict"):
        translator.translate_descriptors(["not a descriptor"])  # type: ignore[list-item]


def test_validate_descriptor_case_insensitive_gate_name() -> None:
    """Gate name validation is case-insensitive (upper-cases before checking)."""
    # lowercase 'h' should be treated as valid 'H'
    _validate_descriptor({"gate": "h", "targets": [0], "controls": [], "params": {}})
    _validate_descriptor({"gate": "RX", "targets": [0], "controls": [], "params": {"angle": 1.0}})
    _validate_descriptor({"gate": "Cnot", "targets": [1], "controls": [0], "params": {}})


def test_validate_descriptor_integer_angle_accepted() -> None:
    """An integer 'angle' value is accepted (numeric types are valid)."""
    _validate_descriptor({"gate": "rx", "targets": [0], "controls": [], "params": {"angle": 1}})


def test_validate_descriptor_tuple_targets_accepted() -> None:
    """Tuple 'targets' and 'controls' are accepted (list-like)."""
    _validate_descriptor({"gate": "h", "targets": (0,), "controls": (), "params": {}})
