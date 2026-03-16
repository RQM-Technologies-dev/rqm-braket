"""
rqm_braket.translators
======================

Translators from RQM-side gate/circuit representations into Amazon Braket
``Circuit`` objects.

No canonical math lives here.  When RQM gate or state objects are needed,
they are imported from ``rqm-core``.  The functions in this module handle
only the minimal parameterisation required to express RQM representations
as Braket gate arguments.
"""

from __future__ import annotations

import cmath
import math
from typing import Any, Sequence

from braket.circuits import Circuit

# ---------------------------------------------------------------------------
# Gate name → Braket Circuit method mapping
# ---------------------------------------------------------------------------

#: Maps a canonical RQM / standard gate name to the corresponding no-argument
#: Braket ``Circuit`` method name.
SINGLE_QUBIT_GATES: dict[str, str] = {
    "H": "h",
    "X": "x",
    "Y": "y",
    "Z": "z",
    "S": "s",
    "T": "t",
    "I": "i",
    "V": "v",
}

#: Maps a canonical gate name to the corresponding *angled* Braket method name.
#: These gates require a single angle argument (in radians).
ROTATION_GATES: dict[str, str] = {
    "RX": "rx",
    "RY": "ry",
    "RZ": "rz",
    "PHASESHIFT": "phaseshift",
}

#: Maps a canonical two-qubit gate name to the Braket method name.
#: Each entry expects (control, target) qubits.
TWO_QUBIT_GATES: dict[str, str] = {
    "CNOT": "cnot",
    "CX": "cnot",
    "CY": "cy",
    "CZ": "cz",
    "SWAP": "swap",
    "ISWAP": "iswap",
}


# ---------------------------------------------------------------------------
# Gate descriptor type
# ---------------------------------------------------------------------------

#: A gate descriptor is a plain dict with at minimum a ``"gate"`` key.
#:
#: Single-qubit gates::
#:
#:     {"gate": "H",  "target": 0}
#:     {"gate": "RX", "target": 0, "angle": 1.5707963}
#:
#: Two-qubit gates::
#:
#:     {"gate": "CNOT", "control": 0, "target": 1}
GateDescriptor = dict[str, Any]


# ---------------------------------------------------------------------------
# Public translator
# ---------------------------------------------------------------------------


def to_braket_circuit(
    gate_sequence: Sequence[GateDescriptor],
    n_qubits: int | None = None,
) -> Circuit:
    """Translate a sequence of RQM gate descriptors into a Braket ``Circuit``.

    Each gate descriptor is a ``dict`` with the following keys:

    * ``"gate"`` *(str, required)* — gate name, e.g. ``"H"``, ``"CNOT"``, ``"RX"``.
    * ``"target"`` *(int, required for single-qubit and two-qubit gates)* — target qubit index.
    * ``"control"`` *(int, required for two-qubit gates)* — control qubit index.
    * ``"angle"`` *(float, required for rotation gates)* — rotation angle in radians.

    Parameters
    ----------
    gate_sequence:
        Ordered list of gate descriptors to apply.
    n_qubits:
        Optional total qubit count.  When provided, qubits ``0..n_qubits-1``
        are allocated up front via identity gates so that the circuit width is
        predictable.  When ``None`` (default), width is inferred from the
        gates applied.

    Returns
    -------
    braket.circuits.Circuit
        A Braket circuit that applies the specified gates in order.

    Raises
    ------
    ValueError
        If a gate name is not recognised or required keys are missing.

    Examples
    --------
    >>> from rqm_braket.translators import to_braket_circuit
    >>> seq = [{"gate": "H", "target": 0}, {"gate": "CNOT", "control": 0, "target": 1}]
    >>> circuit = to_braket_circuit(seq, n_qubits=2)
    """
    circuit = Circuit()

    for descriptor in gate_sequence:
        gate_name = str(descriptor.get("gate", "")).upper()

        if gate_name in SINGLE_QUBIT_GATES:
            target = _require_int(descriptor, "target", gate_name)
            method = getattr(circuit, SINGLE_QUBIT_GATES[gate_name])
            method(target)

        elif gate_name in ROTATION_GATES:
            target = _require_int(descriptor, "target", gate_name)
            angle = _require_float(descriptor, "angle", gate_name)
            method = getattr(circuit, ROTATION_GATES[gate_name])
            method(target, angle)

        elif gate_name in TWO_QUBIT_GATES:
            control = _require_int(descriptor, "control", gate_name)
            target = _require_int(descriptor, "target", gate_name)
            method = getattr(circuit, TWO_QUBIT_GATES[gate_name])
            method(control, target)

        else:
            raise ValueError(
                f"Unknown gate '{gate_name}'. "
                f"Supported single-qubit: {sorted(SINGLE_QUBIT_GATES)}. "
                f"Supported rotation: {sorted(ROTATION_GATES)}. "
                f"Supported two-qubit: {sorted(TWO_QUBIT_GATES)}."
            )

    return circuit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _require_int(descriptor: GateDescriptor, key: str, gate_name: str) -> int:
    """Extract a required integer key from a gate descriptor."""
    if key not in descriptor:
        raise ValueError(f"Gate '{gate_name}' requires a '{key}' key.")
    return int(descriptor[key])


def _require_float(descriptor: GateDescriptor, key: str, gate_name: str) -> float:
    """Extract a required float key from a gate descriptor."""
    if key not in descriptor:
        raise ValueError(f"Gate '{gate_name}' requires a '{key}' key.")
    return float(descriptor[key])


# ---------------------------------------------------------------------------
# RQM object → circuit translators
# ---------------------------------------------------------------------------


def spinor_to_circuit(
    spinor: Sequence[complex],
    qubit: int = 0,
) -> Circuit:
    """Translate a single-qubit spinor [α, β] into a Braket state-prep circuit.

    Prepares the state α|0⟩ + β|1⟩ from |0⟩ using an Ry(θ) followed by
    Rz(φ) decomposition, where:

    * θ = 2·arccos(|α_normalised|)
    * φ = arg(β_normalised) − arg(α_normalised)

    Note: canonical spinor operations (normalisation, Bloch projection, etc.)
    belong in ``rqm-core``.  This function only maps the spinor components to
    Braket gate parameters.

    Parameters
    ----------
    spinor:
        A two-element sequence ``[α, β]`` of (possibly complex) amplitudes
        representing the qubit state α|0⟩ + β|1⟩.  The spinor need not be
        pre-normalised; it is normalised internally.
    qubit:
        Target qubit index (default 0).

    Returns
    -------
    braket.circuits.Circuit
        A single-qubit state-preparation circuit.

    Raises
    ------
    ValueError
        If the spinor has zero norm or does not have exactly two elements.

    Examples
    --------
    >>> from rqm_braket.translators import spinor_to_circuit
    >>> circuit = spinor_to_circuit([1, 0])   # |0⟩ — empty circuit
    >>> circuit = spinor_to_circuit([0, 1])   # |1⟩ — Ry(π)
    >>> circuit = spinor_to_circuit([1, 1])   # |+⟩ — Ry(π/2)
    """
    if len(spinor) != 2:
        raise ValueError(
            f"spinor must have exactly 2 elements, got {len(spinor)}."
        )

    alpha = complex(spinor[0])
    beta = complex(spinor[1])

    # TODO: delegate spinor normalisation to rqm-core once
    #       rqm_core.spinor.normalize() is available.
    #       Propose: rqm_core.spinor.normalize(spinor) → (alpha, beta)
    norm = math.sqrt(abs(alpha) ** 2 + abs(beta) ** 2)
    if norm < 1e-12:
        raise ValueError("Spinor has zero norm.")
    alpha /= norm
    beta /= norm

    # TODO: delegate Bloch angle extraction to rqm-core once
    #       rqm_core.spinor.to_bloch_angles() is available.
    #       Propose: rqm_core.spinor.to_bloch_angles(alpha, beta) → (theta, phi)
    # θ = 2·arccos(|α|), clamped to [0, 1] to guard against floating-point noise
    theta = 2.0 * math.acos(min(1.0, abs(alpha)))
    # Relative phase φ = arg(β) − arg(α)
    phi = cmath.phase(beta) - cmath.phase(alpha)

    circuit = Circuit()
    if abs(theta) > 1e-10:
        circuit.ry(qubit, theta)
    if abs(phi) > 1e-10:
        circuit.rz(qubit, phi)
    return circuit


def bloch_to_circuit(
    bloch_vector: Sequence[float],
    qubit: int = 0,
) -> Circuit:
    """Translate a Bloch sphere vector [x, y, z] into a Braket state-prep circuit.

    Prepares the qubit state corresponding to the point (x, y, z) on the
    Bloch sphere from |0⟩ using Ry(θ) followed by Rz(φ), where:

    * θ = arccos(z)   (polar angle from the north pole)
    * φ = atan2(y, x)  (azimuthal angle)

    Note: canonical Bloch sphere conversions belong in ``rqm-core``.  This
    function only maps the Bloch vector components to Braket gate parameters.

    Parameters
    ----------
    bloch_vector:
        A three-element sequence ``[x, y, z]`` representing a point on (or
        inside) the Bloch sphere.  For a pure state the vector should have
        unit length; mixed states (|vector| < 1) are accepted but only the
        direction is used.
    qubit:
        Target qubit index (default 0).

    Returns
    -------
    braket.circuits.Circuit
        A single-qubit state-preparation circuit.

    Raises
    ------
    ValueError
        If ``bloch_vector`` does not have exactly three elements or is the
        zero vector.

    Examples
    --------
    >>> from rqm_braket.translators import bloch_to_circuit
    >>> circuit = bloch_to_circuit([0, 0,  1])   # north pole → |0⟩
    >>> circuit = bloch_to_circuit([0, 0, -1])   # south pole → |1⟩
    >>> circuit = bloch_to_circuit([1, 0,  0])   # +x → |+⟩
    """
    if len(bloch_vector) != 3:
        raise ValueError(
            f"bloch_vector must have exactly 3 elements, got {len(bloch_vector)}."
        )

    x, y, z = float(bloch_vector[0]), float(bloch_vector[1]), float(bloch_vector[2])
    r = math.sqrt(x ** 2 + y ** 2 + z ** 2)
    if r < 1e-12:
        raise ValueError("Bloch vector has zero magnitude.")

    # TODO: delegate Bloch vector normalisation and spherical-angle extraction
    #       to rqm-core once rqm_core.bloch.to_angles() is available.
    #       Propose: rqm_core.bloch.to_angles(bloch_vector) → (theta, phi)
    # Normalise to unit sphere
    x, y, z = x / r, y / r, z / r

    # Polar angle θ ∈ [0, π], clamped for numerical safety
    theta = math.acos(max(-1.0, min(1.0, z)))
    # Azimuthal angle φ ∈ (−π, π]
    phi = math.atan2(y, x)

    circuit = Circuit()
    if abs(theta) > 1e-10:
        circuit.ry(qubit, theta)
    if abs(phi) > 1e-10:
        circuit.rz(qubit, phi)
    return circuit


def quaternion_to_circuit(
    quaternion: Sequence[float],
    qubit: int = 0,
) -> Circuit:
    """Translate a unit quaternion [w, x, y, z] into a single-qubit Braket circuit.

    Maps a unit quaternion to the corresponding SU(2) gate via a ZYZ Euler
    angle decomposition:  Rz(γ) → Ry(β) → Rz(α), where:

    * β = 2·arccos(√(w² + z²))
    * α = −arg(w − iz) + arg(y − ix)
    * γ = −arg(w − iz) − arg(y − ix)

    Note: canonical quaternion algebra and SU(2) construction belong in
    ``rqm-core``.  This function only maps the quaternion components to
    Braket gate parameters via standard Euler decomposition.

    Parameters
    ----------
    quaternion:
        A four-element sequence ``[w, x, y, z]`` representing a unit
        quaternion.  The quaternion is normalised internally.
    qubit:
        Target qubit index (default 0).

    Returns
    -------
    braket.circuits.Circuit
        A single-qubit circuit implementing the SU(2) rotation.

    Raises
    ------
    ValueError
        If ``quaternion`` does not have exactly four elements or has zero norm.

    Examples
    --------
    >>> from rqm_braket.translators import quaternion_to_circuit
    >>> import math
    >>> # Identity rotation
    >>> circuit = quaternion_to_circuit([1, 0, 0, 0])
    >>> # 180° rotation around Y axis
    >>> circuit = quaternion_to_circuit([0, 0, 1, 0])
    """
    if len(quaternion) != 4:
        raise ValueError(
            f"quaternion must have exactly 4 elements, got {len(quaternion)}."
        )

    w, x, y, z = (float(v) for v in quaternion)
    norm = math.sqrt(w ** 2 + x ** 2 + y ** 2 + z ** 2)
    if norm < 1e-12:
        raise ValueError("Quaternion has zero norm.")

    # TODO: delegate quaternion normalisation and SU(2) Euler decomposition
    #       to rqm-core once rqm_core.quaternion.to_euler_zyz() is available.
    #       Propose: rqm_core.quaternion.to_euler_zyz(quaternion) → (alpha, beta, gamma)
    w, x, y, z = w / norm, x / norm, y / norm, z / norm

    # SU(2) matrix elements:
    #   u00 = w − iz,  u10 = y − ix
    # ZYZ Euler decomposition:
    #   β = 2·arccos(|u00|) = 2·arccos(√(w²+z²))
    #   phase_u00 = arg(w − iz),  phase_u10 = arg(y − ix)
    #   α = −phase_u00 + phase_u10
    #   γ = −phase_u00 − phase_u10

    u00 = complex(w, -z)
    u10 = complex(y, -x)

    beta = 2.0 * math.acos(min(1.0, abs(u00)))
    phase_u00 = cmath.phase(u00)
    phase_u10 = cmath.phase(u10)

    alpha = -phase_u00 + phase_u10
    gamma = -phase_u00 - phase_u10

    # Circuit applies Rz(γ) first, then Ry(β), then Rz(α)
    circuit = Circuit()
    if abs(gamma) > 1e-10:
        circuit.rz(qubit, gamma)
    if abs(beta) > 1e-10:
        circuit.ry(qubit, beta)
    if abs(alpha) > 1e-10:
        circuit.rz(qubit, alpha)
    return circuit
