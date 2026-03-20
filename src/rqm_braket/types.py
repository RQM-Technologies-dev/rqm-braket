"""
rqm_braket.types
================

Type definitions for the rqm-braket bridge.

These types align with the canonical descriptor format produced by
``rqm-compiler``'s ``Circuit.to_descriptors()`` method.

A single gate descriptor is a plain dict:

.. code-block:: python

    {
        "gate": str,          # canonical gate name, e.g. "h", "cx", "u1q"
        "targets": list[int], # target qubit indices
        "controls": list[int],# control qubit indices (empty for single-qubit)
        "params": dict,       # gate parameters, e.g. {"angle": 1.57}
    }

All inputs and outputs in ``rqm-braket`` are designed to be JSON-serializable
to support future API endpoints (``POST /compile``, ``POST /run``).
"""

from __future__ import annotations

from typing import Any

# NOTE:
# Descriptor is the canonical backend-agnostic IR produced by rqm-compiler.
# This format must remain stable and JSON-serializable.
# Backends must consume descriptors but must not redefine them.

#: A single gate descriptor in canonical rqm-compiler format.
Descriptor = dict[str, Any]

#: An ordered list of gate descriptors comprising a compiled program.
DescriptorList = list[Descriptor]
