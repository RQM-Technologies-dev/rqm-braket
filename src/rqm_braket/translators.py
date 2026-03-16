"""
rqm_braket.translators
======================

Translators from RQM-side gate/circuit representations into Amazon Braket
``Circuit`` objects.

No canonical math lives here.  When RQM gate or state objects are needed,
they are imported from ``rqm-core``.
"""

from __future__ import annotations

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
