"""
rqm_braket.translators
======================

Backward-compatibility shim and rqm-core bridge functions.

The canonical translation API has moved to :mod:`rqm_braket.translator`.
This module re-exports the current public symbols for backward compatibility,
provides the dict-accepting :func:`to_braket_circuit` convenience function for
legacy callers, and adds bridge functions that delegate canonical quantum
mathematics to :mod:`rqm_core`.

.. deprecated::
    Import directly from :mod:`rqm_braket.translator` for new code:

    >>> from rqm_braket.translator import RQMGate, compile_to_braket_circuit

Bridge functions (rqm-core delegation)
---------------------------------------
These functions convert rqm-core mathematical objects into Braket circuits.
All canonical mathematics (spinor normalization, Bloch-sphere conversions) is
delegated to :mod:`rqm_core`; only the gate-mapping step lives here.

:func:`spinor_to_circuit`
    Prepare a qubit state from a two-component spinor ``(α, β)``.

:func:`bloch_to_circuit`
    Prepare a qubit state from Bloch-sphere polar angles ``(θ, φ)``.

:func:`quaternion_to_circuit`
    *Stub — not yet implemented.*  Requires ZYZ decomposition support in
    ``rqm-core``.  See the function docstring for details.
"""

from __future__ import annotations

import math
from typing import Any, Sequence, Union

from braket.circuits import Circuit

from rqm_core import Quaternion, state_to_bloch

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
    "spinor_to_circuit",
    "bloch_to_circuit",
    "quaternion_to_circuit",
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


# ---------------------------------------------------------------------------
# rqm-core bridge functions
# ---------------------------------------------------------------------------


def spinor_to_circuit(alpha: complex, beta: complex, target: int = 0) -> Circuit:
    """Prepare a qubit state from a two-component spinor using rqm-core.

    Converts the spinor ``|ψ⟩ = α|0⟩ + β|1⟩`` to a Braket circuit that
    prepares ``|ψ⟩`` starting from ``|0⟩``.

    All spinor and Bloch mathematics is delegated to :mod:`rqm_core`.  Only
    the gate-mapping step (Bloch angles → :class:`~rqm_braket.translator.RQMGate`
    sequence) lives here.

    The state is encoded as ``RY(θ) · RZ(φ)`` applied to ``|0⟩``, where
    ``(θ, φ)`` are the polar angles of the Bloch vector corresponding to
    ``(α, β)``.

    Parameters
    ----------
    alpha:
        Amplitude of ``|0⟩``.  Need not be pre-normalized.
    beta:
        Amplitude of ``|1⟩``.  Need not be pre-normalized.
    target:
        Target qubit index (default 0).

    Returns
    -------
    braket.circuits.Circuit
        A single-qubit circuit that prepares ``|ψ⟩`` from ``|0⟩``.

    Raises
    ------
    ValueError
        If both amplitudes are zero (delegated from :func:`rqm_core.state_to_bloch`).

    Examples
    --------
    >>> import math
    >>> from rqm_braket.translators import spinor_to_circuit
    >>> # Prepare |+⟩ = (|0⟩ + |1⟩) / sqrt(2)
    >>> s = 1.0 / math.sqrt(2)
    >>> circuit = spinor_to_circuit(s, s)
    """
    # Delegate Bloch conversion to rqm-core.
    bx, by, bz = state_to_bloch(alpha, beta)
    # Clamp bz to [-1, 1] before arccos to guard against floating-point
    # rounding errors that can push a pure state's z component just outside
    # the domain (e.g. 1.0000000000000002 for |0⟩).
    theta = math.acos(max(-1.0, min(1.0, bz)))
    phi = math.atan2(by, bx)
    return BraketTranslator().to_circuit([
        RQMGate(gate="RY", target=target, angle=theta),
        RQMGate(gate="RZ", target=target, angle=phi),
    ])


def bloch_to_circuit(theta: float, phi: float, target: int = 0) -> Circuit:
    """Prepare a qubit state from Bloch-sphere polar angles.

    Converts the Bloch-sphere parameterisation
    ``|ψ⟩ = cos(θ/2)|0⟩ + e^{iφ}sin(θ/2)|1⟩`` to a Braket circuit that
    prepares ``|ψ⟩`` starting from ``|0⟩``.

    The encoding is ``RY(θ) · RZ(φ)`` applied to ``|0⟩``.

    Parameters
    ----------
    theta:
        Polar angle (colatitude) in radians.  ``θ = 0`` corresponds to
        the north pole ``|0⟩``; ``θ = π`` to the south pole ``|1⟩``.
    phi:
        Azimuthal angle in radians.
    target:
        Target qubit index (default 0).

    Returns
    -------
    braket.circuits.Circuit
        A single-qubit circuit that prepares the Bloch state ``(θ, φ)``
        from ``|0⟩``.

    Examples
    --------
    >>> import math
    >>> from rqm_braket.translators import bloch_to_circuit
    >>> # Prepare |+⟩ (equator, θ=π/2, φ=0)
    >>> circuit = bloch_to_circuit(math.pi / 2, 0.0)
    """
    return BraketTranslator().to_circuit([
        RQMGate(gate="RY", target=target, angle=theta),
        RQMGate(gate="RZ", target=target, angle=phi),
    ])


def quaternion_to_circuit(q: Quaternion, target: int = 0) -> Circuit:
    """*Stub.* Convert a :class:`~rqm_core.Quaternion` to a Braket circuit.

    .. note::
        **Not yet implemented.**  A correct implementation requires ZYZ
        Euler-angle decomposition of the SU(2) matrix, which is canonical
        SU(2) gate mathematics that belongs in :mod:`rqm_core`.

        TODO: implement once ``rqm-core`` exposes ``Quaternion.to_euler_zyz()``
        or an equivalent ``su2_to_euler_zyz`` helper.

    Parameters
    ----------
    q:
        A :class:`rqm_core.Quaternion` instance representing the target
        single-qubit unitary.
    target:
        Target qubit index (default 0).

    Raises
    ------
    NotImplementedError
        Always.  This function is a placeholder pending the addition of
        ZYZ decomposition support in :mod:`rqm_core`.
    """
    raise NotImplementedError(
        "quaternion_to_circuit requires ZYZ Euler decomposition, which is "
        "canonical SU(2) gate math that belongs in rqm-core.  "
        "TODO: implement once rqm-core exposes Quaternion.to_euler_zyz() "
        "or an equivalent su2_to_euler_zyz helper."
    )
