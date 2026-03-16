"""
rqm_braket.translators
======================

Backward-compatibility shim.

The canonical translation API has moved to :mod:`rqm_braket.translator`.
This module re-exports the current public symbols for backward compatibility
and provides the dict-accepting :func:`to_braket_circuit` convenience
function for legacy callers.

.. deprecated::
    Import directly from :mod:`rqm_braket.translator` for new code:

    >>> from rqm_braket.translator import RQMGate, compile_to_braket_circuit

Note
----
``spinor_to_circuit``, ``bloch_to_circuit``, and ``quaternion_to_circuit``
have been **removed** from this package.  Those functions contained
canonical spinor / Bloch / SU(2) mathematics that belongs in ``rqm-core``.
When ``rqm-core`` exposes the relevant APIs they will be re-added as thin
delegation wrappers.
"""

from __future__ import annotations

from typing import Any, Sequence, Union

from braket.circuits import Circuit

from rqm_braket.translator import (
    ROTATION_GATES,
    SINGLE_QUBIT_GATES,
    TWO_QUBIT_GATES,
    BraketTranslator,
    RQMGate,
    compile_to_braket_circuit,
)

# ---------------------------------------------------------------------------
# Gate descriptor types (kept for backward compat)
# ---------------------------------------------------------------------------

#: A plain ``dict`` gate descriptor.
GateDescriptor = dict[str, Any]

#: Accepted input type for :func:`to_braket_circuit`.
GateInput = Union[RQMGate, GateDescriptor]

__all__ = [
    "RQMGate",
    "GateDescriptor",
    "GateInput",
    "SINGLE_QUBIT_GATES",
    "ROTATION_GATES",
    "TWO_QUBIT_GATES",
    "to_braket_circuit",
    "compile_to_braket_circuit",
]


# ---------------------------------------------------------------------------
# Backward-compat to_braket_circuit (accepts dicts or RQMGate)
# ---------------------------------------------------------------------------


def to_braket_circuit(
    gate_sequence: Sequence[GateInput],
    n_qubits: int | None = None,
) -> Circuit:
    """Translate a sequence of gate descriptors into a Braket ``Circuit``.

    This is the legacy dict-accepting interface.  For new code prefer
    :func:`rqm_braket.translator.compile_to_braket_circuit` with
    :class:`~rqm_braket.translator.RQMGate` instances.

    Each gate descriptor is either an :class:`RQMGate` instance or a ``dict``
    with the following keys:

    * ``"gate"`` — gate name (required).
    * ``"target"`` — target qubit index (required).
    * ``"control"`` — control qubit index (two-qubit gates only).
    * ``"angle"`` — rotation angle in radians (rotation gates only).

    Both forms may be mixed in the same sequence.

    Parameters
    ----------
    gate_sequence:
        Ordered list of gate descriptors.
    n_qubits:
        Ignored.  Kept for backward-API compatibility.

    Returns
    -------
    braket.circuits.Circuit
    """
    normalised = [_normalise_gate_input(raw) for raw in gate_sequence]
    return BraketTranslator().to_circuit(normalised)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _normalise_gate_input(raw: GateInput) -> RQMGate:
    """Convert a dict or :class:`RQMGate` to an :class:`RQMGate`."""
    if isinstance(raw, RQMGate):
        return raw
    gate = str(raw.get("gate", ""))
    target = int(raw["target"])
    control = int(raw["control"]) if "control" in raw else None
    angle = float(raw["angle"]) if "angle" in raw else None
    return RQMGate(gate=gate, target=target, control=control, angle=angle)


def _require_int(descriptor: GateDescriptor, key: str, gate_name: str) -> int:
    """Extract a required integer key from a gate descriptor dict."""
    if key not in descriptor:
        raise ValueError(f"Gate '{gate_name}' requires a '{key}' key.")
    return int(descriptor[key])


def _require_float(descriptor: GateDescriptor, key: str, gate_name: str) -> float:
    """Extract a required float key from a gate descriptor dict."""
    if key not in descriptor:
        raise ValueError(f"Gate '{gate_name}' requires a '{key}' key.")
    return float(descriptor[key])
