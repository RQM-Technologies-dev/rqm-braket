"""
rqm_braket
==========

Amazon Braket backend adapter for the RQM ecosystem.

This package translates compiled quantum programs into Amazon Braket circuits
and provides helpers for executing those circuits on the local simulator or
on AWS Braket devices.

``rqm-braket`` is a **backend bridge**, not a math engine.  All canonical
mathematics (quaternion, spinor, Bloch, SU(2)) belongs in ``rqm-core``.

Public API
----------
BraketBackend
    High-level backend object: compile, run locally, run on AWS device.

BraketTranslator
    Translates compiled programs / gate sequences into Braket ``Circuit``.

RQMGate
    Typed gate descriptor.  Satisfies the ``CompiledInstruction`` protocol.

compile_to_braket_circuit(program)
    Convenience function: translate a compiled program to a Braket circuit.

run_local(program_or_circuit, shots=100)
    Execute on the local Braket state-vector simulator (no AWS credentials).

run_device(program_or_circuit, device_arn, s3_folder, shots=100, **kwargs)
    Execute on a remote AWS Braket device.

BraketResult
    Friendly wrapper around Braket task results.

rqm-core re-exports
-------------------
The following symbols are re-exported from :mod:`rqm_core` for user
convenience.  All canonical mathematics lives in ``rqm-core``.

Quaternion
    Unit-friendly quaternion ``q = w + x·i + y·j + z·k`` from
    :mod:`rqm_core`.

spinor_to_circuit(alpha, beta, target=0)
    Bridge: prepare a qubit state from a spinor; delegates Bloch math to
    :mod:`rqm_core`.

bloch_to_circuit(theta, phi, target=0)
    Bridge: prepare a qubit state from Bloch-sphere polar angles.
"""

from rqm_core import Quaternion

from rqm_braket.backend import BraketBackend
from rqm_braket.execution import run_device, run_local
from rqm_braket.results import BraketResult
from rqm_braket.translator import BraketTranslator, RQMGate, compile_to_braket_circuit
from rqm_braket.translators import bloch_to_circuit, spinor_to_circuit

# Backward-compat re-export (not in __all__)
from rqm_braket.translators import to_braket_circuit  # noqa: F401

__all__ = [
    "BraketBackend",
    "BraketTranslator",
    "RQMGate",
    "compile_to_braket_circuit",
    "run_local",
    "run_device",
    "BraketResult",
    # rqm-core re-exports
    "Quaternion",
    # bridge functions
    "spinor_to_circuit",
    "bloch_to_circuit",
]

__version__ = "0.2.0"
