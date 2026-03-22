"""
rqm_braket.devices
==================

Backward-compatibility shim.

The canonical execution API has moved to :mod:`rqm_braket.execution`.
This module re-exports :func:`run_local`, :func:`run_device`,
:func:`run_device_async`, :func:`get_task_status`, :func:`get_task_result`,
and :func:`list_devices` for backward compatibility.

.. deprecated::
    Import directly from :mod:`rqm_braket.execution` for new code:

    >>> from rqm_braket.execution import run_local, run_device
"""

from rqm_braket.execution import (
    BraketDeviceError,
    get_task_result,
    get_task_status,
    list_devices,
    run_device,
    run_device_async,
    run_descriptors,
    run_local,
)

__all__ = [
    "run_local",
    "run_device",
    "run_device_async",
    "get_task_status",
    "get_task_result",
    "list_devices",
    "run_descriptors",
    "BraketDeviceError",
]
