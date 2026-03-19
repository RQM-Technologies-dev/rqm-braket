"""Tests for rqm-core bridge functions in rqm_braket.translators.

These tests verify that the bridge functions correctly delegate canonical
quantum mathematics to rqm-core and produce valid Braket circuits.
"""

from __future__ import annotations

import math

import numpy as np
import pytest
from braket.circuits import Circuit

import rqm_braket
from rqm_braket.translators import (
    bloch_to_circuit,
    quaternion_to_circuit,
    spinor_to_circuit,
)


# ---------------------------------------------------------------------------
# rqm-core imports available through rqm-braket
# ---------------------------------------------------------------------------


def test_quaternion_importable_from_rqm_braket() -> None:
    """Quaternion re-exported from rqm_braket must be the rqm_core.Quaternion class."""
    from rqm_core import Quaternion as CoreQuaternion

    assert rqm_braket.Quaternion is CoreQuaternion


def test_quaternion_in_all() -> None:
    """Quaternion must be listed in rqm_braket.__all__."""
    assert "Quaternion" in rqm_braket.__all__


def test_quaternion_construction() -> None:
    """Quaternion from rqm_braket can be constructed."""
    q = rqm_braket.Quaternion(1.0, 0.0, 0.0, 0.0)
    assert q.w == 1.0
    assert q.x == 0.0
    assert q.y == 0.0
    assert q.z == 0.0


def test_quaternion_from_axis_angle() -> None:
    """Quaternion.from_axis_angle is accessible via rqm_braket.Quaternion."""
    q = rqm_braket.Quaternion.from_axis_angle("z", math.pi)
    # Should be close to (0, 0, 0, 1) — rotation of π around Z
    assert abs(q.w) < 1e-9
    assert abs(q.z - 1.0) < 1e-9


def test_spinor_to_circuit_in_all() -> None:
    """spinor_to_circuit must be listed in rqm_braket.__all__."""
    assert "spinor_to_circuit" in rqm_braket.__all__


def test_bloch_to_circuit_in_all() -> None:
    """bloch_to_circuit must be listed in rqm_braket.__all__."""
    assert "bloch_to_circuit" in rqm_braket.__all__


# ---------------------------------------------------------------------------
# spinor_to_circuit
# ---------------------------------------------------------------------------


def test_spinor_to_circuit_returns_circuit() -> None:
    """spinor_to_circuit returns a Braket Circuit."""
    s = 1.0 / math.sqrt(2)
    circuit = spinor_to_circuit(s, s)
    assert isinstance(circuit, Circuit)


def test_spinor_to_circuit_qubit_count() -> None:
    """spinor_to_circuit produces a 1-qubit circuit."""
    circuit = spinor_to_circuit(1.0, 0.0)
    assert circuit.qubit_count == 1


def test_spinor_to_circuit_custom_target() -> None:
    """spinor_to_circuit respects the target qubit index."""
    circuit = spinor_to_circuit(1.0, 0.0, target=2)
    assert circuit.qubit_count == 1
    # Braket labels the qubit by its index; verify qubit 2 is used
    assert 2 in [int(q) for q in circuit.qubits]


def test_spinor_to_circuit_north_pole() -> None:
    """|0⟩ spinor (1, 0) produces a valid circuit (RY(0) + RZ(0) ≈ identity)."""
    circuit = spinor_to_circuit(1.0, 0.0)
    assert isinstance(circuit, Circuit)


def test_spinor_to_circuit_south_pole() -> None:
    """|1⟩ spinor (0, 1) produces a valid circuit."""
    circuit = spinor_to_circuit(0.0, 1.0)
    assert isinstance(circuit, Circuit)


def test_spinor_to_circuit_plus_state() -> None:
    """|+⟩ spinor (1/√2, 1/√2) produces a 1-qubit circuit."""
    s = 1.0 / math.sqrt(2)
    circuit = spinor_to_circuit(s, s)
    assert circuit.qubit_count == 1


def test_spinor_to_circuit_unnormalized_accepted() -> None:
    """spinor_to_circuit normalizes the input internally via rqm-core."""
    # (2, 2) is unnormalized but proportional to (1/√2, 1/√2)
    circuit = spinor_to_circuit(2.0, 2.0)
    assert isinstance(circuit, Circuit)
    assert circuit.qubit_count == 1


def test_spinor_to_circuit_zero_raises() -> None:
    """spinor_to_circuit raises ValueError for a zero spinor."""
    with pytest.raises(ValueError):
        spinor_to_circuit(0.0, 0.0)


def test_spinor_to_circuit_complex_amplitudes() -> None:
    """spinor_to_circuit handles complex amplitudes."""
    alpha = complex(1.0 / math.sqrt(2))
    beta = complex(0.0, 1.0 / math.sqrt(2))  # i/√2
    circuit = spinor_to_circuit(alpha, beta)
    assert isinstance(circuit, Circuit)
    assert circuit.qubit_count == 1


def test_spinor_to_circuit_importable_from_top_level() -> None:
    """spinor_to_circuit is accessible from the top-level rqm_braket package."""
    circuit = rqm_braket.spinor_to_circuit(1.0 / math.sqrt(2), 1.0 / math.sqrt(2))
    assert isinstance(circuit, Circuit)


# ---------------------------------------------------------------------------
# bloch_to_circuit
# ---------------------------------------------------------------------------


def test_bloch_to_circuit_returns_circuit() -> None:
    """bloch_to_circuit returns a Braket Circuit."""
    circuit = bloch_to_circuit(math.pi / 2, 0.0)
    assert isinstance(circuit, Circuit)


def test_bloch_to_circuit_qubit_count() -> None:
    """bloch_to_circuit produces a 1-qubit circuit."""
    circuit = bloch_to_circuit(math.pi / 2, 0.0)
    assert circuit.qubit_count == 1


def test_bloch_to_circuit_custom_target() -> None:
    """bloch_to_circuit respects the target qubit index."""
    circuit = bloch_to_circuit(math.pi / 2, 0.0, target=3)
    assert 3 in [int(q) for q in circuit.qubits]


def test_bloch_to_circuit_north_pole() -> None:
    """θ=0 (north pole) produces a valid circuit."""
    circuit = bloch_to_circuit(0.0, 0.0)
    assert isinstance(circuit, Circuit)


def test_bloch_to_circuit_south_pole() -> None:
    """θ=π (south pole) produces a valid circuit."""
    circuit = bloch_to_circuit(math.pi, 0.0)
    assert isinstance(circuit, Circuit)


def test_bloch_to_circuit_equator_x() -> None:
    """θ=π/2, φ=0 (equator, X direction) produces a valid circuit."""
    circuit = bloch_to_circuit(math.pi / 2, 0.0)
    assert isinstance(circuit, Circuit)


def test_bloch_to_circuit_equator_y() -> None:
    """θ=π/2, φ=π/2 (equator, Y direction) produces a valid circuit."""
    circuit = bloch_to_circuit(math.pi / 2, math.pi / 2)
    assert isinstance(circuit, Circuit)


def test_bloch_to_circuit_importable_from_top_level() -> None:
    """bloch_to_circuit is accessible from the top-level rqm_braket package."""
    circuit = rqm_braket.bloch_to_circuit(math.pi / 2, 0.0)
    assert isinstance(circuit, Circuit)


# ---------------------------------------------------------------------------
# quaternion_to_circuit — stub (not yet implemented)
# ---------------------------------------------------------------------------


def test_quaternion_to_circuit_not_implemented() -> None:
    """quaternion_to_circuit raises NotImplementedError (pending rqm-core ZYZ)."""
    q = rqm_braket.Quaternion.from_axis_angle("z", math.pi / 2)
    with pytest.raises(NotImplementedError, match="rqm-core"):
        quaternion_to_circuit(q)


def test_quaternion_to_circuit_not_in_public_all() -> None:
    """quaternion_to_circuit is not in rqm_braket.__all__ until implemented."""
    assert "quaternion_to_circuit" not in rqm_braket.__all__


# ---------------------------------------------------------------------------
# Consistency: spinor_to_circuit vs bloch_to_circuit
# ---------------------------------------------------------------------------


def test_spinor_and_bloch_circuits_same_gate_count() -> None:
    """spinor_to_circuit and bloch_to_circuit produce circuits with the same
    number of instructions for equivalent states."""
    # |+⟩ via spinor
    s = 1.0 / math.sqrt(2)
    c1 = spinor_to_circuit(s, s)
    # |+⟩ via Bloch angles θ=π/2, φ=0
    c2 = bloch_to_circuit(math.pi / 2, 0.0)
    assert len(c1.instructions) == len(c2.instructions)
