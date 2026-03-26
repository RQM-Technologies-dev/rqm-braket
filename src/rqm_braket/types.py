"""
rqm_braket.types
================

Type definitions for the rqm-braket bridge.

These types align with the **compiler-internal descriptor format** produced by
``rqm-compiler``'s ``Circuit.to_descriptors()`` method.  They are **not** the
canonical external circuit schema; that lives in ``rqm-circuits``.  By the
time data reaches ``rqm-braket`` it has already been parsed and validated
upstream (typically by ``rqm-circuits`` and ``rqm-compiler``).

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
# Descriptor is the compiler-internal IR produced by rqm-compiler.
# The public/external circuit schema is owned by rqm-circuits.
# By the time descriptors reach rqm-braket they have already been validated
# and optimized upstream. This format must remain stable and JSON-serializable.
# Backends must consume descriptors but must not redefine them.

#: A single gate descriptor in rqm-compiler internal format.
Descriptor = dict[str, Any]

#: An ordered list of gate descriptors comprising a compiled program.
DescriptorList = list[Descriptor]
