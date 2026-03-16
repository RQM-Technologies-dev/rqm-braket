"""
rqm_braket.devices
==================

Backward-compatibility shim.

The canonical execution API has moved to :mod:`rqm_braket.execution`.
This module re-exports :func:`run_local` and :func:`run_device` for
backward compatibility.

.. deprecated::
    Import directly from :mod:`rqm_braket.execution` for new code:

    >>> from rqm_braket.execution import run_local, run_device
"""

from rqm_braket.execution import run_device, run_local

__all__ = ["run_local", "run_device"]
