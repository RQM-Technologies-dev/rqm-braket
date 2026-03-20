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
* :func:`to_backend_circuit` — compiler-integrated translation that accepts
  an ``rqm_compiler.Circuit``, compiles (and optionally optimizes) it, then
  translates the resulting descriptors into a Braket ``Circuit``.

No canonical quantum mathematics lives here.  All gate parameters must
already be fully resolved; this module only maps instruction metadata to
Braket circuit operations.  SU(2) matrix construction for ``u1q`` is
delegated to :mod:`rqm_core`.
"""

from __future__ import annotations

import numpy as np
from dataclasses import dataclass
from typing import Any, Sequence

from braket.circuits import Circuit

from rqm_braket.types import Descriptor, DescriptorList

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

#: Gates that are silently treated as no-ops (backend does not support them).
NOOP_GATES: frozenset[str] = frozenset({"BARRIER"})


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

        Dispatches based on the type of *instruction*:

        * **Descriptor dict** (produced by ``rqm-compiler``'s
          ``Circuit.to_descriptors()``): routed to :meth:`_apply_descriptor`,
          which also performs validation via :func:`_validate_descriptor`.
          Keys used: ``"gate"``, ``"targets"``, ``"controls"``, ``"params"``.
        * **Attribute-based objects** (:class:`RQMGate` or any object with
          ``gate``, ``target``, ``control``, ``angle`` attributes): handled
          directly in this method.

        Parameters
        ----------
        circuit:
            The Braket circuit being constructed.
        instruction:
            A :class:`CompiledInstruction`-compatible object **or** a
            descriptor dict produced by ``rqm-compiler``'s
            ``Circuit.to_descriptors()``.

        Raises
        ------
        ValueError
            If the gate name is not recognised or a required attribute is
            absent or ``None``.
        TypeError
            If a descriptor dict contains fields of the wrong type (raised
            by :func:`_validate_descriptor` for the dict path).
        """
        # Detect descriptor dict format (targets / controls / params).
        # Objects (e.g. RQMGate) use attribute access (gate, target, control, angle).
        # Plain dicts represent canonical rqm-compiler descriptors and are routed
        # to _apply_descriptor() instead.
        if isinstance(instruction, dict):
            self._apply_descriptor(circuit, instruction)
            return

        gate_name = str(getattr(instruction, "gate", "")).upper()

        if gate_name in NOOP_GATES:
            return  # barrier is a no-op in Braket

        if gate_name == "MEASURE":
            target = _require_int_attr(instruction, "target", gate_name)
            circuit.measure(target)

        elif gate_name == "U1Q":
            target = _require_int_attr(instruction, "target", gate_name)
            angle = getattr(instruction, "angle", None)
            # angle field may carry a quaternion dict or the params may be
            # stored on a ``params`` attribute; both are accepted.
            params = getattr(instruction, "params", None)
            if isinstance(angle, dict):
                params = angle
            if not isinstance(params, dict):
                raise ValueError(
                    "Gate 'U1Q' requires quaternion params "
                    "{'w': ..., 'x': ..., 'y': ..., 'z': ...}."
                )
            self._apply_u1q(circuit, target, params)

        elif gate_name in SINGLE_QUBIT_GATES:
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

    def _apply_descriptor(self, circuit: Circuit, op: Descriptor) -> None:
        """Apply a single canonical descriptor dict to *circuit* in place.

        The descriptor format is the canonical output of
        ``rqm_compiler.Circuit.to_descriptors()``:

        .. code-block:: python

            {
                "gate": str,
                "targets": list[int],
                "controls": list[int],
                "params": dict,
            }

        Parameters
        ----------
        circuit:
            The Braket circuit being constructed.
        op:
            A descriptor dict as produced by ``rqm-compiler``.

        Raises
        ------
        ValueError
            If the descriptor is malformed, the gate name is not recognised,
            or required fields are missing.
        """
        _validate_descriptor(op)

        gate_name = str(op.get("gate", "")).upper()
        targets: list[int] = [int(q) for q in op.get("targets", [])]
        controls: list[int] = [int(q) for q in op.get("controls", [])]
        params: dict[str, Any] = op.get("params", {})

        if gate_name in NOOP_GATES:
            return  # barrier is a no-op in Braket

        if gate_name == "MEASURE":
            for t in targets:
                circuit.measure(t)

        elif gate_name == "U1Q":
            if not targets:
                raise ValueError("Gate 'U1Q' requires at least one target qubit.")
            self._apply_u1q(circuit, targets[0], params)

        elif gate_name in SINGLE_QUBIT_GATES:
            for t in targets:
                getattr(circuit, SINGLE_QUBIT_GATES[gate_name])(t)

        elif gate_name in ROTATION_GATES:
            angle = params.get("angle")
            if angle is None:
                raise ValueError(
                    f"Gate '{gate_name}' requires a 'angle' key in params."
                )
            for t in targets:
                getattr(circuit, ROTATION_GATES[gate_name])(t, float(angle))

        elif gate_name in TWO_QUBIT_GATES:
            if not controls or not targets:
                raise ValueError(
                    f"Gate '{gate_name}' requires both 'controls' and 'targets'."
                )
            getattr(circuit, TWO_QUBIT_GATES[gate_name])(controls[0], targets[0])

        else:
            raise ValueError(
                f"Unknown gate '{gate_name}'. "
                f"Supported single-qubit: {sorted(SINGLE_QUBIT_GATES)}. "
                f"Supported rotation: {sorted(ROTATION_GATES)}. "
                f"Supported two-qubit: {sorted(TWO_QUBIT_GATES)}."
            )

    @staticmethod
    def _apply_u1q(circuit: Circuit, target: int, params: dict[str, Any]) -> None:
        """Apply a ``u1q`` gate from quaternion params.

        Delegates SU(2) matrix construction to :mod:`rqm_core` via
        :meth:`rqm_core.Quaternion.to_su2_matrix`, then applies the result as
        a Braket ``Unitary`` gate.  No quaternion mathematics is implemented
        locally.

        Parameters
        ----------
        circuit:
            The Braket circuit being constructed.
        target:
            Target qubit index.
        params:
            Quaternion components: ``{"w": float, "x": float, "y": float,
            "z": float}``.  Each component defaults to its identity value
            (``w=1.0``, ``x=y=z=0.0``) if omitted, giving the identity
            unitary.
        """
        from rqm_core import Quaternion  # canonical SU(2) math in rqm-core

        w = float(params.get("w", 1.0))
        x = float(params.get("x", 0.0))
        y = float(params.get("y", 0.0))
        z = float(params.get("z", 0.0))
        q = Quaternion(w, x, y, z)
        matrix = np.array(q.to_su2_matrix(), dtype=complex)
        circuit.unitary(matrix=matrix, targets=[target])

    def translate_descriptors(self, descriptors: DescriptorList) -> Circuit:
        """Translate a list of canonical descriptor dicts into a Braket ``Circuit``.

        This method accepts the output of ``rqm_compiler.Circuit.to_descriptors()``
        directly.  Each descriptor is a plain dict:

        .. code-block:: python

            {"gate": str, "targets": list[int], "controls": list[int], "params": dict}

        Parameters
        ----------
        descriptors:
            Ordered list of gate descriptors from ``rqm-compiler``.

        Returns
        -------
        braket.circuits.Circuit
            The resulting Braket circuit.
        """
        circuit = Circuit()
        for op in descriptors:
            self._apply_descriptor(circuit, op)
        return circuit


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


def to_backend_circuit(circuit: Any, *, optimize: bool = False) -> Circuit:
    """Translate an ``rqm_compiler.Circuit`` into a Braket ``Circuit``.

    This is the primary compiler-integrated translation entry point.  It
    accepts an ``rqm_compiler.Circuit``, compiles it (and optionally runs
    optimization passes), then translates the resulting canonical descriptors
    into a Braket ``Circuit``.

    Architecture
    ------------
    .. code-block:: text

        rqm_compiler.Circuit
              ↓
        compile_circuit() / optimize_circuit()
              ↓
        circuit.to_descriptors()
              ↓
        BraketTranslator.translate_descriptors()
              ↓
        braket.circuits.Circuit

    Parameters
    ----------
    circuit:
        An ``rqm_compiler.Circuit`` instance.
    optimize:
        If ``True``, apply optimization passes via
        ``rqm_compiler.optimize_circuit()`` before translation.  If ``False``
        (default), the circuit is compiled without optimization.

    Returns
    -------
    braket.circuits.Circuit
        The resulting Braket circuit.

    Raises
    ------
    ImportError
        If ``rqm-compiler`` is not installed.

    Examples
    --------
    >>> # Requires rqm-compiler to be installed:
    >>> # from rqm_compiler import Circuit
    >>> # from rqm_braket.translator import to_backend_circuit
    >>> # circuit = Circuit(...)
    >>> # braket_circuit = to_backend_circuit(circuit, optimize=True)
    """
    try:
        from rqm_compiler import compile_circuit, optimize_circuit  # type: ignore[import]
    except ImportError as exc:
        raise ImportError(
            "rqm-compiler is required for to_backend_circuit(). "
            "Install it with: pip install rqm-compiler"
        ) from exc

    if optimize:
        optimized_circuit, _report = optimize_circuit(circuit)
        descriptors = optimized_circuit.to_descriptors()
    else:
        compiled = compile_circuit(circuit)
        compiled_circuit = compiled.circuit
        descriptors = compiled_circuit.to_descriptors()
    return BraketTranslator().translate_descriptors(descriptors)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _validate_descriptor(op: Descriptor) -> None:
    """Validate a canonical gate descriptor dict before translation.

    Checks that the descriptor has the required keys, that each field has the
    correct type, and that the gate name is known.  This guard is called by
    :meth:`BraketTranslator._apply_descriptor` so that all descriptor-path
    inputs are validated before any circuit operation is attempted.

    This is particularly important for API-facing code (``POST /run``,
    ``POST /compile``) where descriptors arrive as user-supplied JSON and may
    be malformed or carry unexpected values.

    Parameters
    ----------
    op:
        A descriptor dict to validate.

    Raises
    ------
    TypeError
        If *op* is not a ``dict`` or if any field has the wrong type.
    ValueError
        If a required key is missing, the gate name is empty or unknown, or
        parameter shapes are incorrect for the given gate.
    """
    if not isinstance(op, dict):
        raise TypeError(
            f"Descriptor must be a dict, got {type(op).__name__!r}."
        )

    # --- required keys -------------------------------------------------------
    _REQUIRED_KEYS = {"gate", "targets", "controls", "params"}
    missing = _REQUIRED_KEYS - op.keys()
    if missing:
        raise ValueError(
            f"Descriptor is missing required keys: {sorted(missing)}. "
            f"Expected keys: {sorted(_REQUIRED_KEYS)}."
        )

    # --- field types ---------------------------------------------------------
    gate_raw = op["gate"]
    if not isinstance(gate_raw, str):
        raise TypeError(
            f"Descriptor 'gate' must be a str, got {type(gate_raw).__name__!r}."
        )

    targets = op["targets"]
    if not isinstance(targets, (list, tuple)):
        raise TypeError(
            f"Descriptor 'targets' must be a list, got {type(targets).__name__!r}."
        )

    controls = op["controls"]
    if not isinstance(controls, (list, tuple)):
        raise TypeError(
            f"Descriptor 'controls' must be a list, got {type(controls).__name__!r}."
        )

    params = op["params"]
    if not isinstance(params, dict):
        raise TypeError(
            f"Descriptor 'params' must be a dict, got {type(params).__name__!r}."
        )

    # --- gate name -----------------------------------------------------------
    gate_name = gate_raw.upper()
    if not gate_name:
        raise ValueError("Descriptor 'gate' must not be empty.")

    _ALL_KNOWN_GATES = (
        set(SINGLE_QUBIT_GATES)
        | set(ROTATION_GATES)
        | set(TWO_QUBIT_GATES)
        | NOOP_GATES
        | {"MEASURE", "U1Q"}
    )
    if gate_name not in _ALL_KNOWN_GATES:
        raise ValueError(
            f"Unknown gate '{gate_name}' in descriptor. "
            f"Known gates: {sorted(_ALL_KNOWN_GATES)}."
        )

    # --- parameter shapes ----------------------------------------------------
    if gate_name in ROTATION_GATES:
        if "angle" not in params:
            raise ValueError(
                f"Descriptor for rotation gate '{gate_name}' requires "
                f"'angle' in params."
            )
        angle_val = params["angle"]
        if not isinstance(angle_val, (int, float)):
            raise TypeError(
                f"Descriptor param 'angle' for gate '{gate_name}' must be a "
                f"number, got {type(angle_val).__name__!r}."
            )

    if gate_name == "U1Q":
        for key in ("w", "x", "y", "z"):
            if key not in params:
                raise ValueError(
                    f"Descriptor for 'U1Q' requires '{key}' in params. "
                    f"Expected: {{'w': float, 'x': float, 'y': float, 'z': float}}."
                )
            val = params[key]
            if not isinstance(val, (int, float)):
                raise TypeError(
                    f"Descriptor param '{key}' for gate 'U1Q' must be a "
                    f"number, got {type(val).__name__!r}."
                )


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
