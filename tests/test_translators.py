"""Tests for rqm_braket.translators — backward-compat shim.

These tests verify that the legacy dict-based ``to_braket_circuit`` interface
and the ``RQMGate`` dataclass continue to work via the backward-compat shim.

Canonical math functions (``spinor_to_circuit``, ``bloch_to_circuit``,
``quaternion_to_circuit``) have been removed from this package and are
therefore not tested here.
"""

import math

import pytest
from braket.circuits import Circuit

from rqm_braket.translators import (
    RQMGate,
    to_braket_circuit,
)


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
    with pytest.raises((ValueError, KeyError)):
        to_braket_circuit(seq)


def test_missing_angle_raises() -> None:
    seq = [{"gate": "RX", "target": 0}]
    with pytest.raises(ValueError, match="angle"):
        to_braket_circuit(seq)


def test_missing_control_raises() -> None:
    seq = [{"gate": "CNOT", "target": 1}]
    with pytest.raises(ValueError, match="control"):
        to_braket_circuit(seq)


def test_empty_sequence() -> None:
    """An empty gate sequence produces an empty circuit."""
    circuit = to_braket_circuit([])
    assert isinstance(circuit, Circuit)
    assert circuit.qubit_count == 0


# ---------------------------------------------------------------------------
# RQMGate dataclass
# ---------------------------------------------------------------------------


def test_rqmgate_single_qubit() -> None:
    """RQMGate works as a typed alternative to dict descriptors."""
    seq = [RQMGate(gate="H", target=0)]
    circuit = to_braket_circuit(seq)
    assert isinstance(circuit, Circuit)
    assert circuit.qubit_count == 1


def test_rqmgate_rotation() -> None:
    """RQMGate with angle builds a rotation gate."""
    seq = [RQMGate(gate="RX", target=0, angle=math.pi / 2)]
    circuit = to_braket_circuit(seq)
    assert isinstance(circuit, Circuit)
    assert circuit.qubit_count == 1


def test_rqmgate_two_qubit() -> None:
    """RQMGate with control builds a two-qubit gate."""
    seq = [RQMGate(gate="CNOT", target=1, control=0)]
    circuit = to_braket_circuit(seq)
    assert isinstance(circuit, Circuit)
    assert circuit.qubit_count == 2


def test_rqmgate_bell_sequence() -> None:
    """H + CNOT via RQMGate produces a valid Bell-state circuit."""
    seq = [
        RQMGate(gate="H", target=0),
        RQMGate(gate="CNOT", target=1, control=0),
    ]
    circuit = to_braket_circuit(seq, n_qubits=2)
    assert isinstance(circuit, Circuit)
    assert circuit.qubit_count == 2


def test_rqmgate_mixed_with_dicts() -> None:
    """RQMGate and plain dict descriptors can be mixed in the same sequence."""
    seq: list = [
        RQMGate(gate="H", target=0),
        {"gate": "CNOT", "control": 0, "target": 1},
    ]
    circuit = to_braket_circuit(seq)
    assert isinstance(circuit, Circuit)
    assert circuit.qubit_count == 2


def test_rqmgate_defaults() -> None:
    """Optional fields default to None."""
    gate = RQMGate(gate="H", target=0)
    assert gate.gate == "H"
    assert gate.target == 0
    assert gate.control is None
    assert gate.angle is None


def test_rqmgate_case_insensitive() -> None:
    """Gate names are normalised to upper-case, so lowercase works."""
    seq = [RQMGate(gate="h", target=0)]
    circuit = to_braket_circuit(seq)
    assert isinstance(circuit, Circuit)


def test_rqmgate_unknown_gate_raises() -> None:
    """RQMGate with an unrecognised gate name raises ValueError."""
    seq = [RQMGate(gate="FOOBAR", target=0)]
    with pytest.raises(ValueError, match="Unknown gate"):
        to_braket_circuit(seq)


def test_rqmgate_importable_from_top_level() -> None:
    """RQMGate is accessible from the top-level rqm_braket package."""
    import rqm_braket

    assert rqm_braket.RQMGate is RQMGate
    gate = rqm_braket.RQMGate(gate="H", target=0)
    assert gate.gate == "H"

