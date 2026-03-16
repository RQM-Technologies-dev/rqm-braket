"""
rqm_braket.execution
====================

Execution helpers for running compiled programs or Braket circuits on the
local simulator or on real AWS Braket devices.

Both functions accept either:

* a Braket ``Circuit`` directly, or
* a ``CompiledProgram``-compatible object (anything with an ``.instructions``
  attribute), or
* a sequence of ``CompiledInstruction``-compatible objects.

When a compiled program or instruction sequence is provided it is translated
to a ``Circuit`` automatically via :class:`~rqm_braket.translator.BraketTranslator`.

No canonical math lives here.  These are thin wrappers around the Braket
device and task APIs.
"""

from __future__ import annotations

from typing import Any, Tuple

from braket.circuits import Circuit

from rqm_braket.results import BraketResult
from rqm_braket.translator import BraketTranslator


def run_local(
    program_or_circuit: Circuit | Any,
    shots: int = 100,
) -> BraketResult:
    """Execute on the local Braket state-vector simulator.

    This function does **not** require AWS credentials and runs entirely
    offline.  It is the recommended way to validate circuits in CI and
    during development.

    Parameters
    ----------
    program_or_circuit:
        Either a Braket ``Circuit``, a ``CompiledProgram``-compatible object
        (has ``.instructions``), or a sequence of
        ``CompiledInstruction``-compatible objects.
    shots:
        Number of measurement shots (default 100).

    Returns
    -------
    BraketResult
        Wrapped result containing counts, probabilities, and metadata.

    Examples
    --------
    >>> from rqm_braket.circuits import bell_circuit
    >>> from rqm_braket.execution import run_local
    >>> result = run_local(bell_circuit(), shots=200)
    >>> print(result.counts)
    """
    from braket.devices import LocalSimulator

    circuit = _resolve_circuit(program_or_circuit)
    device = LocalSimulator()
    task = device.run(circuit, shots=shots)
    return BraketResult(task.result())


def run_device(
    program_or_circuit: Circuit | Any,
    device_arn: str,
    s3_folder: Tuple[str, str],
    shots: int = 100,
    **kwargs: Any,
) -> BraketResult:
    """Execute on a remote AWS Braket device.

    Requires valid AWS credentials and a configured Braket-enabled region.

    Parameters
    ----------
    program_or_circuit:
        Either a Braket ``Circuit``, a ``CompiledProgram``-compatible object
        (has ``.instructions``), or a sequence of
        ``CompiledInstruction``-compatible objects.
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
    >>> from rqm_braket.execution import run_device
    >>> result = run_device(
    ...     bell_circuit(),
    ...     device_arn="arn:aws:braket:::device/quantum-simulator/amazon/sv1",
    ...     s3_folder=("my-bucket", "my-prefix"),
    ...     shots=100,
    ... )
    >>> print(result.counts)
    """
    from braket.aws import AwsDevice  # imported lazily to allow offline use

    circuit = _resolve_circuit(program_or_circuit)
    device = AwsDevice(device_arn)
    task = device.run(circuit, s3_folder, shots=shots, **kwargs)
    return BraketResult(task.result())


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _resolve_circuit(program_or_circuit: Circuit | Any) -> Circuit:
    """Return a Braket ``Circuit`` from *program_or_circuit*.

    If the argument is already a ``Circuit``, it is returned unchanged.
    Otherwise it is translated via :class:`~rqm_braket.translator.BraketTranslator`.
    """
    if isinstance(program_or_circuit, Circuit):
        return program_or_circuit
    return BraketTranslator().to_circuit(program_or_circuit)
