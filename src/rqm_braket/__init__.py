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
    High-level backend object: compile, run locally, run on AWS device,
    submit asynchronous jobs, run from descriptors.

BraketTranslator
    Translates compiled programs / gate sequences into Braket ``Circuit``.

RQMGate
    Typed gate descriptor.  Satisfies the ``CompiledInstruction`` protocol.

compile_to_braket_circuit(program)
    Convenience function: translate a compiled program to a Braket circuit.

to_backend_circuit(circuit, *, optimize=False)
    Compiler-integrated translation: accepts an ``rqm_compiler.Circuit``,
    compiles it (and optionally optimizes it), then returns a Braket circuit.
    Requires ``rqm-compiler`` to be installed.

run_local(program_or_circuit, shots=100)
    Execute on the local Braket state-vector simulator (no AWS credentials).

run_device(program_or_circuit, device_arn, s3_folder, shots=100, **kwargs)
    Execute on a remote AWS Braket device (synchronous).

run_device_async(program_or_circuit, device_arn, s3_folder, shots=100, **kwargs)
    Submit to a remote AWS Braket device and return the task ARN (asynchronous).

get_task_status(task_arn)
    Return the current status of an AWS Braket task.

get_task_result(task_arn)
    Retrieve the result of a completed AWS Braket task.

list_devices(device_types=None)
    List available AWS Braket devices with optional type filter.

run_descriptors(descriptors, shots=100, backend="local", ...)
    Translate canonical descriptors and execute the resulting circuit.

BraketResult
    Friendly wrapper around Braket task results.

BraketDeviceError
    Exception raised when a Braket device or task operation fails.

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
from rqm_braket.execution import (
    BraketDeviceError,
    get_task_result,
    get_task_status,
    list_devices,
    run_descriptors,
    run_device,
    run_device_async,
    run_local,
)
from rqm_braket.results import BraketResult
from rqm_braket.translator import BraketTranslator, RQMGate, compile_to_braket_circuit, to_backend_circuit
from rqm_braket.translators import bloch_to_circuit, spinor_to_circuit

# Backward-compat re-export (not in __all__)
from rqm_braket.translators import to_braket_circuit  # noqa: F401

__all__ = [
    "BraketBackend",
    "BraketTranslator",
    "RQMGate",
    "compile_to_braket_circuit",
    "to_backend_circuit",
    "run_local",
    "run_device",
    "run_device_async",
    "get_task_status",
    "get_task_result",
    "list_devices",
    "run_descriptors",
    "BraketResult",
    "BraketDeviceError",
    # rqm-core re-exports
    "Quaternion",
    # bridge functions
    "spinor_to_circuit",
    "bloch_to_circuit",
]

__version__ = "0.2.0"
