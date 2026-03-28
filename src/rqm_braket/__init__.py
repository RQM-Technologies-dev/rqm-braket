"""
rqm_braket
==========

Amazon Braket lowering and execution bridge for the RQM ecosystem.

``rqm-braket`` is **downstream of rqm-compiler** in the RQM stack.  It
receives compiler-optimized circuit representations and translates them into
Amazon Braket circuit and task objects, then executes them on the local
simulator or on AWS Braket devices.

Stack position::

    rqm-circuits  ← public/external circuit schema (not owned here)
         ↓
    rqm-compiler  ← optimization + internal IR (not owned here)
         ↓
    rqm-braket    ← Braket lowering + execution (this package)

``rqm-braket`` is a **backend bridge**.  It does not implement canonical
mathematics (that belongs in ``rqm-core``), does not define the public
circuit schema (that belongs in ``rqm-circuits``), and does not perform
circuit optimization (that belongs in ``rqm-compiler``).

The base package import is intentionally lightweight and does not require
Flask.  Flask integration lives in :mod:`rqm_braket.api` and is loaded only
when API-specific symbols (for example ``api_blueprint``) are accessed.
"""

from __future__ import annotations

from typing import Any

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
    "api_blueprint",
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


def __getattr__(name: str) -> Any:
    """Lazily expose optional API symbols.

    ``rqm_braket.api`` depends on Flask, which is declared in the optional
    ``[api]`` extra.  Delaying the import keeps ``import rqm_braket`` working
    in base installations that do not include Flask.
    """
    if name == "api_blueprint":
        from rqm_braket.api import api_blueprint

        return api_blueprint
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__version__ = "0.2.0"
