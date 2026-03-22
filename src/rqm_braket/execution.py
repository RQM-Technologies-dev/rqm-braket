"""
rqm_braket.execution
====================

Execution helpers for running compiled programs or Braket circuits on the
local simulator or on real AWS Braket devices.

All functions accept either:

* a Braket ``Circuit`` directly, or
* a ``CompiledProgram``-compatible object (anything with an ``.instructions``
  attribute), or
* a sequence of ``CompiledInstruction``-compatible objects.

When a compiled program or instruction sequence is provided it is translated
to a ``Circuit`` automatically via :class:`~rqm_braket.translator.BraketTranslator`.

No canonical math lives here.  These are thin wrappers around the Braket
device and task APIs.

Async and device-discovery functions lazy-import ``braket.aws`` so that the
local simulator and offline tests remain credential-free.
"""

from __future__ import annotations

from typing import Any, Literal, Tuple

from braket.circuits import Circuit

from rqm_braket.results import BraketResult
from rqm_braket.translator import BraketTranslator
from rqm_braket.types import DescriptorList


# ---------------------------------------------------------------------------
# Custom exception
# ---------------------------------------------------------------------------


class BraketDeviceError(RuntimeError):
    """Raised when a Braket device or task operation fails.

    Wraps low-level AWS / Braket SDK exceptions with a friendlier message
    that includes context (e.g., device ARN or task ID).
    """


# ---------------------------------------------------------------------------
# Synchronous execution helpers
# ---------------------------------------------------------------------------


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
    """Execute on a remote AWS Braket device (synchronous).

    Blocks until the task completes and returns a :class:`BraketResult`.
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
    BraketDeviceError
        If the device is unreachable or the task fails.
    ImportError
        If ``amazon-braket-sdk`` is not installed.

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
    try:
        device = AwsDevice(device_arn)
        task = device.run(circuit, s3_folder, shots=shots, **kwargs)
        return BraketResult(task.result())
    except Exception as exc:
        raise BraketDeviceError(
            f"Failed to run circuit on device '{device_arn}': {exc}"
        ) from exc


# ---------------------------------------------------------------------------
# Asynchronous execution helpers
# ---------------------------------------------------------------------------


def run_device_async(
    program_or_circuit: Circuit | Any,
    device_arn: str,
    s3_folder: Tuple[str, str],
    shots: int = 100,
    **kwargs: Any,
) -> str:
    """Submit a circuit to a remote AWS Braket device and return the task ARN.

    Unlike :func:`run_device`, this function does **not** block until the
    task completes.  It returns the task ARN immediately so that the caller
    can poll the task status with :func:`get_task_status` and retrieve the
    result with :func:`get_task_result` when ready.

    Parameters
    ----------
    program_or_circuit:
        Either a Braket ``Circuit``, a ``CompiledProgram``-compatible object
        (has ``.instructions``), or a sequence of
        ``CompiledInstruction``-compatible objects.
    device_arn:
        ARN of the target device.
    s3_folder:
        A ``(bucket, key_prefix)`` tuple for Braket result storage.
    shots:
        Number of measurement shots (default 100).
    **kwargs:
        Additional keyword arguments forwarded to ``AwsDevice.run()``.

    Returns
    -------
    str
        The task ARN (Amazon Resource Name) identifying the submitted job.
        Pass this to :func:`get_task_status` or :func:`get_task_result`.

    Raises
    ------
    BraketDeviceError
        If the device is unreachable or task submission fails.
    ImportError
        If ``amazon-braket-sdk`` is not installed.

    Examples
    --------
    >>> from rqm_braket.circuits import bell_circuit
    >>> from rqm_braket.execution import run_device_async, get_task_status
    >>> task_arn = run_device_async(
    ...     bell_circuit(),
    ...     device_arn="arn:aws:braket:::device/quantum-simulator/amazon/sv1",
    ...     s3_folder=("my-bucket", "my-prefix"),
    ...     shots=100,
    ... )
    >>> status = get_task_status(task_arn)
    >>> print(status)  # e.g. "QUEUED", "RUNNING", "COMPLETED"
    """
    from braket.aws import AwsDevice  # imported lazily to allow offline use

    circuit = _resolve_circuit(program_or_circuit)
    try:
        device = AwsDevice(device_arn)
        task = device.run(circuit, s3_folder, shots=shots, **kwargs)
        return task.id
    except Exception as exc:
        raise BraketDeviceError(
            f"Failed to submit circuit to device '{device_arn}': {exc}"
        ) from exc


def get_task_status(task_arn: str) -> str:
    """Return the current status of an AWS Braket task.

    Queries the Braket service for the live state of the task identified by
    *task_arn* and returns a status string.

    Parameters
    ----------
    task_arn:
        ARN of the task as returned by :func:`run_device_async`.

    Returns
    -------
    str
        One of ``"CREATED"``, ``"QUEUED"``, ``"RUNNING"``, ``"COMPLETED"``,
        ``"FAILED"``, or ``"CANCELLED"``.

    Raises
    ------
    BraketDeviceError
        If the task cannot be found or the status query fails.
    ImportError
        If ``amazon-braket-sdk`` is not installed.

    Examples
    --------
    >>> from rqm_braket.execution import get_task_status
    >>> status = get_task_status("arn:aws:braket:us-east-1:123456789012:task/abc")
    >>> print(status)  # "QUEUED"
    """
    from braket.aws import AwsQuantumTask  # imported lazily to allow offline use

    try:
        task = AwsQuantumTask(task_arn)
        return task.state()
    except Exception as exc:
        raise BraketDeviceError(
            f"Failed to retrieve status for task '{task_arn}': {exc}"
        ) from exc


def get_task_result(task_arn: str) -> BraketResult:
    """Retrieve the result of a completed AWS Braket task.

    Blocks until the task is complete if it has not yet finished.  Use
    :func:`get_task_status` first to check whether the task is ready before
    calling this function.

    Parameters
    ----------
    task_arn:
        ARN of the task as returned by :func:`run_device_async`.

    Returns
    -------
    BraketResult
        Wrapped result containing counts, probabilities, and metadata.

    Raises
    ------
    BraketDeviceError
        If the task cannot be found, has failed, or result retrieval fails.
    ImportError
        If ``amazon-braket-sdk`` is not installed.

    Examples
    --------
    >>> from rqm_braket.execution import get_task_result
    >>> result = get_task_result("arn:aws:braket:us-east-1:123456789012:task/abc")
    >>> print(result.counts)
    """
    from braket.aws import AwsQuantumTask  # imported lazily to allow offline use

    try:
        task = AwsQuantumTask(task_arn)
        return BraketResult(task.result())
    except Exception as exc:
        raise BraketDeviceError(
            f"Failed to retrieve result for task '{task_arn}': {exc}"
        ) from exc


# ---------------------------------------------------------------------------
# Device discovery
# ---------------------------------------------------------------------------


def list_devices(
    device_types: list[str] | None = None,
) -> list[dict[str, Any]]:
    """List available AWS Braket devices.

    Queries the Braket service for all available devices and returns a
    JSON-serializable list of device information dicts.  Requires valid AWS
    credentials and a configured Braket-enabled region.

    Parameters
    ----------
    device_types:
        Optional filter list.  Each entry must be one of ``"QPU"``,
        ``"SIMULATOR"``.  When ``None`` (default), all device types are
        returned.

    Returns
    -------
    list[dict[str, Any]]
        Each dict contains the following keys:

        * ``"deviceArn"`` — the device ARN.
        * ``"deviceName"`` — human-readable name.
        * ``"deviceType"`` — ``"QPU"`` or ``"SIMULATOR"``.
        * ``"status"`` — ``"ONLINE"``, ``"OFFLINE"``, or ``"RETIRED"``.
        * ``"providerName"`` — the provider (e.g. ``"Amazon"``, ``"IonQ"``).

    Raises
    ------
    BraketDeviceError
        If the device listing query fails.
    ImportError
        If ``amazon-braket-sdk`` is not installed.

    Examples
    --------
    >>> from rqm_braket.execution import list_devices
    >>> devices = list_devices(device_types=["SIMULATOR"])
    >>> for d in devices:
    ...     print(d["deviceName"], d["status"])
    """
    from braket.aws import AwsDevice  # imported lazily to allow offline use

    try:
        statuses = ["ONLINE", "OFFLINE"]
        if device_types is not None:
            types_upper = [t.upper() for t in device_types]
            results = AwsDevice.get_devices(types=types_upper, statuses=statuses)
        else:
            results = AwsDevice.get_devices(statuses=statuses)

        devices: list[dict[str, Any]] = []
        for dev in results:
            devices.append(
                {
                    "deviceArn": dev.arn,
                    "deviceName": dev.name,
                    "deviceType": dev.type.value if hasattr(dev.type, "value") else str(dev.type),
                    "status": dev.status,
                    "providerName": dev.provider_name,
                }
            )
        return devices
    except Exception as exc:
        raise BraketDeviceError(f"Failed to list devices: {exc}") from exc


# ---------------------------------------------------------------------------
# Descriptor-first execution
# ---------------------------------------------------------------------------


def run_descriptors(
    descriptors: DescriptorList,
    shots: int = 100,
    backend: Literal["local", "device"] = "local",
    device_arn: str | None = None,
    s3_folder: Tuple[str, str] | None = None,
    **kwargs: Any,
) -> BraketResult:
    """Translate canonical descriptors and execute the resulting circuit.

    This is the primary entry point for the **API layer** (e.g. ``rqm-api``).
    It accepts the canonical descriptor format produced by
    ``rqm_compiler.Circuit.to_descriptors()``, converts them to a Braket
    ``Circuit``, and runs it on the requested backend.

    Parameters
    ----------
    descriptors:
        Ordered list of canonical gate descriptors.  Each descriptor is a
        plain dict with keys ``"gate"``, ``"targets"``, ``"controls"``, and
        ``"params"``.
    shots:
        Number of measurement shots (default 100).
    backend:
        ``"local"`` (default) runs on the local state-vector simulator and
        does not require AWS credentials.  ``"device"`` submits to a real
        AWS Braket device; *device_arn* and *s3_folder* must be provided.
    device_arn:
        ARN of the target device (required when *backend* is ``"device"``).
    s3_folder:
        ``(bucket, key_prefix)`` tuple for Braket result storage (required
        when *backend* is ``"device"``).
    **kwargs:
        Additional keyword arguments forwarded to the underlying execution
        function.

    Returns
    -------
    BraketResult
        Wrapped result containing counts, probabilities, and metadata.

    Raises
    ------
    ValueError
        If *backend* is ``"device"`` but *device_arn* or *s3_folder* are not
        provided.
    BraketDeviceError
        If the device is unreachable or the task fails (device backend only).

    Examples
    --------
    >>> from rqm_braket.execution import run_descriptors
    >>> descriptors = [
    ...     {"gate": "h", "targets": [0], "controls": [], "params": {}},
    ...     {"gate": "cx", "targets": [1], "controls": [0], "params": {}},
    ... ]
    >>> result = run_descriptors(descriptors, shots=200)
    >>> print(result.counts)  # e.g. Counter({'00': 103, '11': 97})
    """
    translator = BraketTranslator()
    circuit = translator.translate_descriptors(descriptors)

    if backend == "local":
        return run_local(circuit, shots=shots)

    if backend == "device":
        if device_arn is None:
            raise ValueError(
                "run_descriptors: 'device_arn' must be provided when backend='device'."
            )
        if s3_folder is None:
            raise ValueError(
                "run_descriptors: 's3_folder' must be provided when backend='device'."
            )
        return run_device(circuit, device_arn, s3_folder, shots=shots, **kwargs)

    raise ValueError(
        f"run_descriptors: unknown backend '{backend}'. Must be 'local' or 'device'."
    )


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
