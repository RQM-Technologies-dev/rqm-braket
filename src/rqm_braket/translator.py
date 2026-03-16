"""
rqm_braket.translator
=====================

Translation layer from compiled gate-instruction sequences into Amazon Braket
``Circuit`` objects.

This module defines the primary translation API used by ``rqm-braket``:

* :class:`CompiledInstruction` — structural protocol for a single compiler
  instruction (compatible with ``rqm-compiler`` output).
* :class:`CompiledProgram` — structural protocol for a compiled quantum
  program (compatible with ``rqm-compiler`` output).
* :class:`RQMGate` — concrete typed gate descriptor that satisfies
  ``CompiledInstruction``.  Use this when ``rqm-compiler`` is not yet
  available or when building gate sequences manually.
* :class:`BraketTranslator` — translates a compiled program or a sequence
  of instructions into a Braket ``Circuit``.
* :func:`compile_to_braket_circuit` — module-level convenience wrapper
  around ``BraketTranslator``.

No canonical quantum mathematics lives here.  All gate parameters must
already be fully resolved; this module only maps instruction metadata to
Braket circuit operations.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from braket.circuits import Circuit

# ---------------------------------------------------------------------------
# Gate name → Braket Circuit method mapping
# ---------------------------------------------------------------------------

#: Maps a canonical gate name to the corresponding no-argument Braket
#: ``Circuit`` method name.
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

#: Maps a canonical gate name to the corresponding single-angle Braket method.
#: These gates require one angle argument (radians).
ROTATION_GATES: dict[str, str] = {
    "RX": "rx",
    "RY": "ry",
    "RZ": "rz",
    "PHASESHIFT": "phaseshift",
    "PHASE": "phaseshift",
}

#: Maps a canonical two-qubit gate name to the Braket method name.
#: Each entry expects ``(control, target)`` qubits.
TWO_QUBIT_GATES: dict[str, str] = {
    "CNOT": "cnot",
    "CX": "cnot",
    "CY": "cy",
    "CZ": "cz",
    "SWAP": "swap",
    "ISWAP": "iswap",
}


# ---------------------------------------------------------------------------
# Compiler boundary protocols
# ---------------------------------------------------------------------------


class CompiledInstruction:
    """Structural protocol for a single compiled gate instruction.

    Any object that exposes ``gate``, ``target``, ``control``, and ``angle``
    attributes satisfies this protocol.  Objects from ``rqm-compiler`` and
    instances of :class:`RQMGate` both qualify.

    Attributes
    ----------
    gate:
        Canonical upper-case gate name, e.g. ``"H"``, ``"CNOT"``, ``"RX"``.
    target:
        Target qubit index.
    control:
        Control qubit index for two-qubit gates, or ``None``.
    angle:
        Rotation angle in radians for parameterised gates, or ``None``.
    """

    gate: str
    target: int
    control: int | None
    angle: float | None


class CompiledProgram:
    """Structural protocol for a compiled quantum program.

    Any object that exposes an ``instructions`` attribute containing a
    sequence of :class:`CompiledInstruction`-compatible objects satisfies
    this protocol.  Objects from ``rqm-compiler`` qualify.

    Attributes
    ----------
    instructions:
        Ordered sequence of compiled gate instructions.
    """

    instructions: Sequence[Any]


# ---------------------------------------------------------------------------
# RQMGate — concrete typed instruction
# ---------------------------------------------------------------------------


@dataclass
class RQMGate:
    """Typed gate descriptor that satisfies the :class:`CompiledInstruction`
    protocol.

    Use :class:`RQMGate` to construct gate sequences manually when
    ``rqm-compiler`` output is not yet available.  Instances are accepted
    directly by :class:`BraketTranslator` and by the :func:`compile_to_braket_circuit`
    convenience function.

    Attributes
    ----------
    gate:
        Gate name, e.g. ``"H"``, ``"CNOT"``, ``"RX"``.  Case-insensitive
        (normalised to upper-case internally).
    target:
        Target qubit index.
    control:
        Control qubit index (two-qubit gates only; ``None`` for single-qubit
        gates).
    angle:
        Rotation angle in radians (rotation gates only; ``None`` otherwise).

    Examples
    --------
    >>> from rqm_braket.translator import RQMGate, compile_to_braket_circuit
    >>> seq = [
    ...     RQMGate(gate="H", target=0),
    ...     RQMGate(gate="CNOT", target=1, control=0),
    ... ]
    >>> circuit = compile_to_braket_circuit(seq)
    """

    gate: str
    target: int
    control: int | None = None
    angle: float | None = None


# ---------------------------------------------------------------------------
# BraketTranslator
# ---------------------------------------------------------------------------

# NOTE:
# Primary input type is rqm-compiler CompiledProgram.
# RQMGate and dict support are transitional and may be removed in a future release.


class BraketTranslator:
    """Translates compiled quantum programs into Amazon Braket ``Circuit`` objects.

    The translator accepts either:

    * A :class:`CompiledProgram`-compatible object (anything with an
      ``.instructions`` attribute), or
    * A plain ``Sequence`` of :class:`CompiledInstruction`-compatible objects
      (anything with ``gate``, ``target``, ``control``, and ``angle``
      attributes).

    :class:`RQMGate` instances satisfy the instruction protocol and can be
    passed directly.

    Examples
    --------
    >>> from rqm_braket.translator import BraketTranslator, RQMGate
    >>> translator = BraketTranslator()
    >>> circuit = translator.to_circuit([
    ...     RQMGate(gate="H", target=0),
    ...     RQMGate(gate="CNOT", target=1, control=0),
    ... ])
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def to_circuit(
        self,
        program: Any,
    ) -> Circuit:
        """Translate *program* into a Braket ``Circuit``.

        Parameters
        ----------
        program:
            Either a :class:`CompiledProgram`-compatible object (has an
            ``.instructions`` attribute) or an iterable of
            :class:`CompiledInstruction`-compatible objects.

        Returns
        -------
        braket.circuits.Circuit
            The resulting Braket circuit.

        Raises
        ------
        ValueError
            If a gate name is unrecognised or a required attribute is missing.
        """
        circuit = Circuit()
        instructions = _get_instructions(program)
        for instruction in instructions:
            self._apply_instruction(circuit, instruction)
        return circuit

    def _apply_instruction(
        self,
        circuit: Circuit,
        instruction: Any,
    ) -> None:
        """Apply a single compiled instruction to *circuit* in place.

        Parameters
        ----------
        circuit:
            The Braket circuit being constructed.
        instruction:
            A :class:`CompiledInstruction`-compatible object with ``gate``,
            ``target``, ``control``, and ``angle`` attributes.

        Raises
        ------
        ValueError
            If the gate name is not recognised or a required attribute is
            absent or ``None``.
        """
        gate_name = str(getattr(instruction, "gate", "")).upper()

        if gate_name in SINGLE_QUBIT_GATES:
            target = _require_int_attr(instruction, "target", gate_name)
            getattr(circuit, SINGLE_QUBIT_GATES[gate_name])(target)

        elif gate_name in ROTATION_GATES:
            target = _require_int_attr(instruction, "target", gate_name)
            angle = _require_float_attr(instruction, "angle", gate_name)
            getattr(circuit, ROTATION_GATES[gate_name])(target, angle)

        elif gate_name in TWO_QUBIT_GATES:
            control = _require_int_attr(instruction, "control", gate_name)
            target = _require_int_attr(instruction, "target", gate_name)
            getattr(circuit, TWO_QUBIT_GATES[gate_name])(control, target)

        else:
            raise ValueError(
                f"Unknown gate '{gate_name}'. "
                f"Supported single-qubit: {sorted(SINGLE_QUBIT_GATES)}. "
                f"Supported rotation: {sorted(ROTATION_GATES)}. "
                f"Supported two-qubit: {sorted(TWO_QUBIT_GATES)}."
            )


# ---------------------------------------------------------------------------
# Module-level convenience
# ---------------------------------------------------------------------------


def compile_to_braket_circuit(program: Any) -> Circuit:
    """Translate a compiled program or gate sequence into a Braket ``Circuit``.

    Convenience wrapper around :class:`BraketTranslator`.  Accepts the same
    inputs as :meth:`BraketTranslator.to_circuit`.

    Parameters
    ----------
    program:
        A :class:`CompiledProgram`-compatible object or an iterable of
        :class:`CompiledInstruction`-compatible objects (e.g.
        :class:`RQMGate` instances).

    Returns
    -------
    braket.circuits.Circuit

    Examples
    --------
    >>> from rqm_braket.translator import RQMGate, compile_to_braket_circuit
    >>> circuit = compile_to_braket_circuit([
    ...     RQMGate(gate="H", target=0),
    ...     RQMGate(gate="CNOT", target=1, control=0),
    ... ])
    """
    return BraketTranslator().to_circuit(program)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _get_instructions(program: Any) -> Any:
    """Return the instruction iterable from *program*.

    If *program* has an ``.instructions`` attribute (i.e. it looks like a
    :class:`CompiledProgram`), return that attribute.  Otherwise treat
    *program* itself as a sequence of instructions.
    """
    if hasattr(program, "instructions"):
        return program.instructions
    return program


def _require_int_attr(instruction: Any, attr: str, gate_name: str) -> int:
    """Extract a required integer attribute from *instruction*."""
    value = getattr(instruction, attr, None)
    if value is None:
        raise ValueError(f"Gate '{gate_name}' requires a '{attr}' attribute.")
    return int(value)


def _require_float_attr(instruction: Any, attr: str, gate_name: str) -> float:
    """Extract a required float attribute from *instruction*."""
    value = getattr(instruction, attr, None)
    if value is None:
        raise ValueError(f"Gate '{gate_name}' requires an '{attr}' attribute.")
    return float(value)
