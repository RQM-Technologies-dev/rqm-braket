"""
rqm_braket.devices
==================

Execution helpers for running Braket circuits on the local simulator or
on real AWS Braket devices.

No canonical math lives here.  These are thin wrappers around the Braket
device and task APIs.
"""

from __future__ import annotations

from typing import Any, Tuple

from braket.circuits import Circuit
from braket.devices import LocalSimulator

from rqm_braket.results import BraketResult


def run_local(circuit: Circuit, shots: int = 100) -> BraketResult:
    """Execute *circuit* on the local Braket state-vector simulator.

    This function does **not** require AWS credentials and runs entirely
    offline.  It is the recommended way to validate circuits in CI and
    during development.

    Parameters
    ----------
    circuit:
        The Braket ``Circuit`` to execute.
    shots:
        Number of measurement shots (default 100).

    Returns
    -------
    BraketResult
        Wrapped result containing counts, probabilities, and metadata.

    Examples
    --------
    >>> from rqm_braket.circuits import bell_circuit
    >>> from rqm_braket.devices import run_local
    >>> result = run_local(bell_circuit(), shots=200)
    >>> print(result.counts)
    """
    device = LocalSimulator()
    task = device.run(circuit, shots=shots)
    return BraketResult(task.result())


def run_device(
    circuit: Circuit,
    device_arn: str,
    s3_folder: Tuple[str, str],
    shots: int = 100,
    **kwargs: Any,
) -> BraketResult:
    """Execute *circuit* on a remote AWS Braket device.

    Requires valid AWS credentials and a configured Braket-enabled region.

    Parameters
    ----------
    circuit:
        The Braket ``Circuit`` to execute.
    device_arn:
        ARN of the target device, e.g.
        ``"arn:aws:braket:::device/quantum-simulator/amazon/sv1"``.
    s3_folder:
        A ``(bucket, key_prefix)`` tuple identifying the S3 location where
        Braket will write task results.
    shots:
        Number of measurement shots (default 100).
    **kwargs:
        Additional keyword arguments forwarded to ``AwsDevice.run()``.

    Returns
    -------
    BraketResult
        Wrapped result containing counts, probabilities, and metadata.

    Raises
    ------
    ImportError
        If ``amazon-braket-sdk`` is not installed.
    Exception
        Propagates any AWS / Braket SDK exception on task submission or
        result retrieval.

    Examples
    --------
    >>> from rqm_braket.circuits import bell_circuit
    >>> from rqm_braket.devices import run_device
    >>> result = run_device(
    ...     bell_circuit(),
    ...     device_arn="arn:aws:braket:::device/quantum-simulator/amazon/sv1",
    ...     s3_folder=("my-bucket", "my-prefix"),
    ...     shots=100,
    ... )
    >>> print(result.counts)
    """
    from braket.aws import AwsDevice  # imported lazily to allow offline use

    device = AwsDevice(device_arn)
    task = device.run(circuit, s3_folder, shots=shots, **kwargs)
    return BraketResult(task.result())
