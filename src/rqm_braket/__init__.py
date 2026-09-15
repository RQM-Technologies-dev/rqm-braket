"""Amazon Braket lowering and execution bridge for the RQM ecosystem."""
from __future__ import annotations
from typing import Any
from rqm_core import Quaternion
from rqm_braket.backend import BraketBackend
from rqm_braket.execution import BraketDeviceError, get_task_result, get_task_status, list_devices, run_descriptors, run_device, run_device_async, run_local
from rqm_braket.results import BraketResult
from rqm_braket.translator import BraketTranslator, RQMGate, compile_to_braket_circuit, to_backend_circuit
from rqm_braket.translators import bloch_to_circuit, spinor_to_circuit
from rqm_braket.relational import lower_relational_descriptors
from rqm_braket.translators import to_braket_circuit  # noqa: F401

__all__ = ["api_blueprint", "BraketBackend", "BraketTranslator", "RQMGate", "compile_to_braket_circuit", "to_backend_circuit", "lower_relational_descriptors", "run_local", "run_device", "run_device_async", "get_task_status", "get_task_result", "list_devices", "run_descriptors", "BraketResult", "BraketDeviceError", "Quaternion", "spinor_to_circuit", "bloch_to_circuit"]

def __getattr__(name: str) -> Any:
    if name == "api_blueprint":
        from rqm_braket.api import api_blueprint
        return api_blueprint
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

try:
    from importlib.metadata import PackageNotFoundError, version
    __version__ = version("rqm-braket")
except PackageNotFoundError:
    __version__ = "0.0.0+unknown"
