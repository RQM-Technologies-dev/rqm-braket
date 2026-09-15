"""Lower compiler relational primitives to Amazon Braket without owning their math."""
from __future__ import annotations
from typing import Any, Sequence
from braket.circuits import Circuit

_PAIR_METHOD = {"rxx": "xx", "ryy": "yy", "rzz": "zz"}

def lower_relational_descriptors(descriptors: Sequence[dict[str, Any]], circuit: Circuit | None = None) -> Circuit:
    """Append canonical RXX/RYY/RZZ descriptors to a Braket circuit.

    rqm-compiler/rqm-entanglement decide the representation. This adapter only
    maps the standard pair rotations to Braket XX/YY/ZZ gates.
    """
    out = circuit or Circuit()
    for op in descriptors:
        gate = str(op.get("gate", "")).lower()
        if gate not in _PAIR_METHOD:
            raise ValueError(f"expected relational pair rotation, got {gate!r}")
        targets = list(op.get("targets", []))
        params = op.get("params", {})
        if len(targets) != 2 or not isinstance(params, dict) or "angle" not in params:
            raise ValueError(f"{gate} requires two targets and params.angle")
        getattr(out, _PAIR_METHOD[gate])(targets[0], targets[1], float(params["angle"]))
    return out
