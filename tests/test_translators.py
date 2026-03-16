"""Tests for rqm_braket.translators."""

import math

import pytest
from braket.circuits import Circuit

from rqm_braket.translators import to_braket_circuit


# ---------------------------------------------------------------------------
# Basic single-qubit gates
# ---------------------------------------------------------------------------


def test_h_gate() -> None:
    """H gate produces a valid Braket circuit."""
    seq = [{"gate": "H", "target": 0}]
    circuit = to_braket_circuit(seq)
    assert isinstance(circuit, Circuit)
    assert circuit.qubit_count == 1


def test_x_gate() -> None:
    seq = [{"gate": "X", "target": 0}]
    circuit = to_braket_circuit(seq)
    assert circuit.qubit_count == 1


def test_y_gate() -> None:
    seq = [{"gate": "Y", "target": 0}]
    circuit = to_braket_circuit(seq)
    assert isinstance(circuit, Circuit)


def test_z_gate() -> None:
    seq = [{"gate": "Z", "target": 0}]
    circuit = to_braket_circuit(seq)
    assert isinstance(circuit, Circuit)


def test_s_gate() -> None:
    seq = [{"gate": "S", "target": 0}]
    circuit = to_braket_circuit(seq)
    assert isinstance(circuit, Circuit)


def test_t_gate() -> None:
    seq = [{"gate": "T", "target": 0}]
    circuit = to_braket_circuit(seq)
    assert isinstance(circuit, Circuit)


def test_i_gate() -> None:
    seq = [{"gate": "I", "target": 0}]
    circuit = to_braket_circuit(seq)
    assert isinstance(circuit, Circuit)


# ---------------------------------------------------------------------------
# Rotation gates
# ---------------------------------------------------------------------------


def test_rx_gate() -> None:
    seq = [{"gate": "RX", "target": 0, "angle": math.pi / 2}]
    circuit = to_braket_circuit(seq)
    assert isinstance(circuit, Circuit)


def test_ry_gate() -> None:
    seq = [{"gate": "RY", "target": 0, "angle": math.pi}]
    circuit = to_braket_circuit(seq)
    assert isinstance(circuit, Circuit)


def test_rz_gate() -> None:
    seq = [{"gate": "RZ", "target": 0, "angle": math.pi / 4}]
    circuit = to_braket_circuit(seq)
    assert isinstance(circuit, Circuit)


# ---------------------------------------------------------------------------
# Two-qubit gates
# ---------------------------------------------------------------------------


def test_cnot_gate() -> None:
    """CNOT gate produces a 2-qubit circuit."""
    seq = [{"gate": "CNOT", "control": 0, "target": 1}]
    circuit = to_braket_circuit(seq)
    assert isinstance(circuit, Circuit)
    assert circuit.qubit_count == 2


def test_cx_alias() -> None:
    """CX is an alias for CNOT."""
    seq = [{"gate": "CX", "control": 0, "target": 1}]
    circuit = to_braket_circuit(seq)
    assert circuit.qubit_count == 2


def test_cz_gate() -> None:
    seq = [{"gate": "CZ", "control": 0, "target": 1}]
    circuit = to_braket_circuit(seq)
    assert isinstance(circuit, Circuit)


def test_swap_gate() -> None:
    seq = [{"gate": "SWAP", "control": 0, "target": 1}]
    circuit = to_braket_circuit(seq)
    assert isinstance(circuit, Circuit)


# ---------------------------------------------------------------------------
# Bell-state sequence
# ---------------------------------------------------------------------------


def test_bell_sequence() -> None:
    """H + CNOT gate sequence produces a Bell-state circuit."""
    seq = [
        {"gate": "H", "target": 0},
        {"gate": "CNOT", "control": 0, "target": 1},
    ]
    circuit = to_braket_circuit(seq, n_qubits=2)
    assert isinstance(circuit, Circuit)
    assert circuit.qubit_count == 2


# ---------------------------------------------------------------------------
# Multi-gate sequence
# ---------------------------------------------------------------------------


def test_multi_gate_sequence() -> None:
    """A multi-gate sequence builds correctly."""
    seq = [
        {"gate": "H", "target": 0},
        {"gate": "RZ", "target": 0, "angle": math.pi / 2},
        {"gate": "CNOT", "control": 0, "target": 1},
        {"gate": "T", "target": 1},
    ]
    circuit = to_braket_circuit(seq)
    assert isinstance(circuit, Circuit)
    assert circuit.qubit_count == 2


# ---------------------------------------------------------------------------
# Case insensitivity
# ---------------------------------------------------------------------------


def test_lowercase_gate_name() -> None:
    """Gate names should be case-insensitive."""
    seq = [{"gate": "h", "target": 0}]
    circuit = to_braket_circuit(seq)
    assert isinstance(circuit, Circuit)


def test_mixed_case_gate_name() -> None:
    seq = [{"gate": "cNoT", "control": 0, "target": 1}]
    circuit = to_braket_circuit(seq)
    assert isinstance(circuit, Circuit)


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


def test_unknown_gate_raises() -> None:
    seq = [{"gate": "FOOBAR", "target": 0}]
    with pytest.raises(ValueError, match="Unknown gate"):
        to_braket_circuit(seq)


def test_missing_target_raises() -> None:
    seq = [{"gate": "H"}]
    with pytest.raises(ValueError, match="requires a 'target'"):
        to_braket_circuit(seq)


def test_missing_angle_raises() -> None:
    seq = [{"gate": "RX", "target": 0}]
    with pytest.raises(ValueError, match="requires a 'angle'"):
        to_braket_circuit(seq)


def test_missing_control_raises() -> None:
    seq = [{"gate": "CNOT", "target": 1}]
    with pytest.raises(ValueError, match="requires a 'control'"):
        to_braket_circuit(seq)


def test_empty_sequence() -> None:
    """An empty gate sequence produces an empty circuit."""
    circuit = to_braket_circuit([])
    assert isinstance(circuit, Circuit)
    assert circuit.qubit_count == 0
