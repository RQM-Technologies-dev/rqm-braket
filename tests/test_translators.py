"""Tests for rqm_braket.translators."""

import math

import pytest
from braket.circuits import Circuit

from rqm_braket.translators import (
    bloch_to_circuit,
    quaternion_to_circuit,
    spinor_to_circuit,
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


# ---------------------------------------------------------------------------
# spinor_to_circuit
# ---------------------------------------------------------------------------


def test_spinor_zero_state_is_identity() -> None:
    """|0⟩ spinor [1, 0] produces an empty circuit (no gates needed)."""
    circuit = spinor_to_circuit([1, 0])
    assert isinstance(circuit, Circuit)
    # No instructions — the state is already |0⟩
    assert len(circuit.instructions) == 0


def test_spinor_one_state() -> None:
    """|1⟩ spinor [0, 1] produces a non-empty circuit."""
    circuit = spinor_to_circuit([0, 1])
    assert isinstance(circuit, Circuit)
    assert len(circuit.instructions) > 0


def test_spinor_superposition() -> None:
    """|+⟩ spinor [1, 1] (unnormalised) produces a valid circuit."""
    circuit = spinor_to_circuit([1, 1])
    assert isinstance(circuit, Circuit)


def test_spinor_complex_amplitudes() -> None:
    """Complex spinor components are accepted."""
    import cmath
    circuit = spinor_to_circuit([1, 1j])
    assert isinstance(circuit, Circuit)


def test_spinor_custom_qubit() -> None:
    """The qubit index is respected."""
    circuit = spinor_to_circuit([0, 1], qubit=2)
    assert isinstance(circuit, Circuit)
    assert 2 in circuit.qubits


def test_spinor_zero_norm_raises() -> None:
    with pytest.raises(ValueError, match="zero norm"):
        spinor_to_circuit([0, 0])


def test_spinor_wrong_length_raises() -> None:
    with pytest.raises(ValueError, match="2 elements"):
        spinor_to_circuit([1, 0, 0])


def test_spinor_returns_circuit_type() -> None:
    circuit = spinor_to_circuit([1, 0])
    assert isinstance(circuit, Circuit)


# ---------------------------------------------------------------------------
# bloch_to_circuit
# ---------------------------------------------------------------------------


def test_bloch_north_pole_is_identity() -> None:
    """North pole [0, 0, 1] represents |0⟩ — no gates needed."""
    circuit = bloch_to_circuit([0, 0, 1])
    assert isinstance(circuit, Circuit)
    assert len(circuit.instructions) == 0


def test_bloch_south_pole() -> None:
    """South pole [0, 0, -1] represents |1⟩ — non-empty circuit."""
    circuit = bloch_to_circuit([0, 0, -1])
    assert isinstance(circuit, Circuit)
    assert len(circuit.instructions) > 0


def test_bloch_plus_x() -> None:
    """+x Bloch vector represents |+⟩."""
    circuit = bloch_to_circuit([1, 0, 0])
    assert isinstance(circuit, Circuit)


def test_bloch_plus_y() -> None:
    circuit = bloch_to_circuit([0, 1, 0])
    assert isinstance(circuit, Circuit)


def test_bloch_custom_qubit() -> None:
    circuit = bloch_to_circuit([1, 0, 0], qubit=1)
    assert isinstance(circuit, Circuit)
    assert 1 in circuit.qubits


def test_bloch_zero_vector_raises() -> None:
    with pytest.raises(ValueError, match="zero magnitude"):
        bloch_to_circuit([0, 0, 0])


def test_bloch_wrong_length_raises() -> None:
    with pytest.raises(ValueError, match="3 elements"):
        bloch_to_circuit([0, 1])


def test_bloch_unnormalised_vector() -> None:
    """Unnormalised vectors are accepted (direction is used, magnitude ignored)."""
    circuit = bloch_to_circuit([0, 0, 5])
    assert isinstance(circuit, Circuit)
    assert len(circuit.instructions) == 0  # same direction as north pole


# ---------------------------------------------------------------------------
# quaternion_to_circuit
# ---------------------------------------------------------------------------


def test_quaternion_identity_is_empty() -> None:
    """Identity quaternion [1, 0, 0, 0] produces an empty circuit."""
    circuit = quaternion_to_circuit([1, 0, 0, 0])
    assert isinstance(circuit, Circuit)
    assert len(circuit.instructions) == 0


def test_quaternion_y_rotation() -> None:
    """180° rotation around Y axis [0, 0, 1, 0] produces a circuit."""
    circuit = quaternion_to_circuit([0, 0, 1, 0])
    assert isinstance(circuit, Circuit)
    assert len(circuit.instructions) > 0


def test_quaternion_x_rotation() -> None:
    """90° rotation around X axis."""
    half = math.sqrt(0.5)
    circuit = quaternion_to_circuit([half, half, 0, 0])
    assert isinstance(circuit, Circuit)


def test_quaternion_custom_qubit() -> None:
    circuit = quaternion_to_circuit([1, 0, 0, 0], qubit=3)
    assert isinstance(circuit, Circuit)


def test_quaternion_zero_norm_raises() -> None:
    with pytest.raises(ValueError, match="zero norm"):
        quaternion_to_circuit([0, 0, 0, 0])


def test_quaternion_wrong_length_raises() -> None:
    with pytest.raises(ValueError, match="4 elements"):
        quaternion_to_circuit([1, 0, 0])


def test_quaternion_unnormalised_accepted() -> None:
    """Unnormalised quaternions are accepted (normalised internally)."""
    circuit = quaternion_to_circuit([2, 0, 0, 0])  # same as [1, 0, 0, 0]
    assert isinstance(circuit, Circuit)
    assert len(circuit.instructions) == 0
