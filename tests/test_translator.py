"""Tests for rqm_braket.translator — BraketTranslator and RQMGate."""

import math

import pytest
from braket.circuits import Circuit

from rqm_braket.translator import (
    BraketTranslator,
    RQMGate,
    compile_to_braket_circuit,
)


# ---------------------------------------------------------------------------
# RQMGate dataclass
# ---------------------------------------------------------------------------


def test_rqmgate_minimal_construction() -> None:
    """RQMGate can be constructed with only gate and target."""
    gate = RQMGate(gate="H", target=0)
    assert gate.gate == "H"
    assert gate.target == 0
    assert gate.control is None
    assert gate.angle is None


def test_rqmgate_full_construction() -> None:
    """RQMGate can hold all four fields."""
    gate = RQMGate(gate="RX", target=1, control=None, angle=math.pi / 2)
    assert gate.gate == "RX"
    assert gate.target == 1
    assert gate.control is None
    assert abs(gate.angle - math.pi / 2) < 1e-12


def test_rqmgate_two_qubit() -> None:
    """RQMGate correctly stores a two-qubit gate with control qubit."""
    gate = RQMGate(gate="CNOT", target=1, control=0)
    assert gate.gate == "CNOT"
    assert gate.control == 0
    assert gate.target == 1


def test_rqmgate_equality() -> None:
    """Two RQMGate instances with identical fields compare equal (dataclass)."""
    a = RQMGate(gate="H", target=0)
    b = RQMGate(gate="H", target=0)
    assert a == b


# ---------------------------------------------------------------------------
# BraketTranslator — single-qubit fixed gates
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("gate_name", ["H", "X", "Y", "Z", "S", "T", "I", "V"])
def test_single_qubit_fixed_gate(gate_name: str) -> None:
    """Each fixed single-qubit gate produces a 1-qubit circuit."""
    translator = BraketTranslator()
    circuit = translator.to_circuit([RQMGate(gate=gate_name, target=0)])
    assert isinstance(circuit, Circuit)
    assert circuit.qubit_count == 1


# ---------------------------------------------------------------------------
# BraketTranslator — rotation gates
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "gate_name",
    ["RX", "RY", "RZ", "PHASESHIFT", "PHASE"],
)
def test_rotation_gate(gate_name: str) -> None:
    """Each rotation gate produces a 1-qubit circuit when given an angle."""
    translator = BraketTranslator()
    circuit = translator.to_circuit(
        [RQMGate(gate=gate_name, target=0, angle=math.pi / 4)]
    )
    assert isinstance(circuit, Circuit)
    assert circuit.qubit_count == 1


def test_rotation_gate_missing_angle_raises() -> None:
    """A rotation gate without an angle raises ValueError."""
    translator = BraketTranslator()
    with pytest.raises(ValueError, match="requires an 'angle'"):
        translator.to_circuit([RQMGate(gate="RX", target=0)])


# ---------------------------------------------------------------------------
# BraketTranslator — two-qubit gates
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "gate_name",
    ["CNOT", "CX", "CY", "CZ", "SWAP", "ISWAP"],
)
def test_two_qubit_gate(gate_name: str) -> None:
    """Each two-qubit gate produces a 2-qubit circuit."""
    translator = BraketTranslator()
    circuit = translator.to_circuit(
        [RQMGate(gate=gate_name, target=1, control=0)]
    )
    assert isinstance(circuit, Circuit)
    assert circuit.qubit_count == 2


def test_two_qubit_gate_missing_control_raises() -> None:
    """A two-qubit gate without a control qubit raises ValueError."""
    translator = BraketTranslator()
    with pytest.raises(ValueError, match="requires a 'control'"):
        translator.to_circuit([RQMGate(gate="CNOT", target=1)])


# ---------------------------------------------------------------------------
# BraketTranslator — unknown gate
# ---------------------------------------------------------------------------


def test_unknown_gate_raises() -> None:
    """An unrecognised gate name raises ValueError."""
    translator = BraketTranslator()
    with pytest.raises(ValueError, match="Unknown gate"):
        translator.to_circuit([RQMGate(gate="MAGIC", target=0)])


# ---------------------------------------------------------------------------
# BraketTranslator — multi-gate sequences
# ---------------------------------------------------------------------------


def test_bell_state_sequence() -> None:
    """H + CNOT produces the Bell-state circuit with 2 qubits."""
    translator = BraketTranslator()
    seq = [
        RQMGate(gate="H", target=0),
        RQMGate(gate="CNOT", target=1, control=0),
    ]
    circuit = translator.to_circuit(seq)
    assert circuit.qubit_count == 2


def test_empty_sequence_returns_empty_circuit() -> None:
    """An empty sequence yields an empty circuit."""
    translator = BraketTranslator()
    circuit = translator.to_circuit([])
    assert isinstance(circuit, Circuit)
    assert circuit.qubit_count == 0


def test_mixed_gate_sequence() -> None:
    """A sequence mixing fixed, rotation, and two-qubit gates is handled."""
    translator = BraketTranslator()
    seq = [
        RQMGate(gate="H", target=0),
        RQMGate(gate="RX", target=0, angle=math.pi / 2),
        RQMGate(gate="CNOT", target=1, control=0),
        RQMGate(gate="RZ", target=1, angle=math.pi),
    ]
    circuit = translator.to_circuit(seq)
    assert circuit.qubit_count == 2


# ---------------------------------------------------------------------------
# BraketTranslator — CompiledProgram protocol (duck typing)
# ---------------------------------------------------------------------------


class _FakeCompiledProgram:
    """Minimal stub that satisfies the CompiledProgram structural protocol."""

    def __init__(self, instructions: list) -> None:
        self.instructions = instructions


def test_to_circuit_accepts_compiled_program() -> None:
    """to_circuit accepts any object with an .instructions attribute."""
    program = _FakeCompiledProgram([
        RQMGate(gate="H", target=0),
        RQMGate(gate="CNOT", target=1, control=0),
    ])
    translator = BraketTranslator()
    circuit = translator.to_circuit(program)
    assert circuit.qubit_count == 2


# ---------------------------------------------------------------------------
# compile_to_braket_circuit convenience function
# ---------------------------------------------------------------------------


def test_compile_to_braket_circuit_sequence() -> None:
    """compile_to_braket_circuit works with a plain sequence of RQMGate."""
    seq = [RQMGate(gate="H", target=0), RQMGate(gate="CNOT", target=1, control=0)]
    circuit = compile_to_braket_circuit(seq)
    assert isinstance(circuit, Circuit)
    assert circuit.qubit_count == 2


def test_compile_to_braket_circuit_compiled_program() -> None:
    """compile_to_braket_circuit works with a CompiledProgram-like object."""
    program = _FakeCompiledProgram([RQMGate(gate="X", target=0)])
    circuit = compile_to_braket_circuit(program)
    assert circuit.qubit_count == 1


# ---------------------------------------------------------------------------
# Case-insensitive gate names
# ---------------------------------------------------------------------------


def test_lowercase_gate_name_accepted() -> None:
    """Gate names are normalised to upper-case; lower-case input is accepted."""
    translator = BraketTranslator()
    circuit = translator.to_circuit([RQMGate(gate="h", target=0)])
    assert circuit.qubit_count == 1


def test_mixed_case_gate_name_accepted() -> None:
    """Mixed-case gate names are accepted."""
    translator = BraketTranslator()
    circuit = translator.to_circuit([RQMGate(gate="Cnot", target=1, control=0)])
    assert circuit.qubit_count == 2
