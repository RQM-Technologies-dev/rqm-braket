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

import os

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


# Capability checked by durable callers before any provider action. This is not
# a package version: older 0.2.3 candidates do not implement this contract.
DURABLE_SUBMISSION_CONTRACT_VERSION = 1


class _SubmissionSession:
    """Per-call SDK session view; never mutate a shared session or retry a create."""

    def __init__(self, session: Any, client_token: str, expected_action: str) -> None:
        self._session = session
        self._client_token = client_token
        self._expected_action = expected_action
        self._attempted = False

    def __getattr__(self, name: str) -> Any:
        return getattr(self._session, name)

    def create_quantum_task(self, **kwargs: Any) -> str:
        if self._attempted:
            raise BraketDeviceError("A submission session cannot create another task")
        if kwargs.get("action") != self._expected_action:
            raise BraketDeviceError("SDK action differs from frozen circuit serialization")
        self._attempted = True
        kwargs["clientToken"] = self._client_token
        return self._session.create_quantum_task(**kwargs)


def serialize_circuit_action(program_or_circuit: Circuit | Any) -> str:
    """Return the exact default OpenQASM action JSON without provider access.

    Durable submission checks this action again at dispatch. Persist its hash
    with the request for explicit-ARN recovery; metadata tags alone are not proof.
    """
    from braket.circuits.serialization import IRType
    circuit = _resolve_circuit(program_or_circuit)
    return circuit.to_ir(ir_type=IRType.OPENQASM,
                         serialization_properties=None, gate_definitions={}).json()


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

    Notes
    -----
    ``run_local`` enables a temporary local-only compatibility path for
    raw ``U1Q`` descriptors/instructions by allowing translation through
    ``Circuit.unitary(...)``. Hardware-facing helpers intentionally do not
    enable that path.

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

    circuit = _resolve_circuit(program_or_circuit, allow_local_u1q_unitary=True)
    device = LocalSimulator()
    task = device.run(circuit, shots=shots)
    return BraketResult(task.result())


def run_device(
    program_or_circuit: Circuit | Any,
    device_arn: str,
    s3_folder: Tuple[str, str],
    shots: int = 100,
    *,
    aws_session: Any = None,
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
        device = AwsDevice(device_arn, **({'aws_session': aws_session} if aws_session is not None else {}))
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
    *,
    aws_session: Any = None,
    client_token: str | None = None,
    tags: dict[str, str] | None = None,
    expected_action: str | None = None,
    **kwargs: Any,
) -> str:
    """Submit a circuit to a remote AWS Braket device and return the task ARN.

    ``client_token`` opts into durable submission: callers must persist it
    before calling, supply a region-matched session, and treat any submission
    exception as potentially accepted. This helper never retries or searches
    for a replacement task. SDK transport retries, if enabled by the caller,
    must reuse this exact token. No simulator fallback is performed.

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

    # SDK **kwargs are task-constructor options, not CreateQuantumTask fields.
    # Reject the tempting camel-case spelling before it can cause an uncertain
    # accepted submission followed by a constructor TypeError.
    if "clientToken" in kwargs:
        raise ValueError("Use client_token, not clientToken")
    if client_token is not None:
        if any(os.environ.get(name) for name in (
            "AMZN_BRAKET_JOB_TOKEN", "AMZN_BRAKET_RESERVATION_DEVICE_ARN",
            "AMZN_BRAKET_RESERVATION_TIME_WINDOW_ARN",
        )):
            raise ValueError("Durable submission rejects ambient job/reservation context")
        if (not isinstance(client_token, str) or not client_token
                or len(client_token) > 64 or not all(
                    c.isascii() and (c.isalnum() or c in "_-")
                    for c in client_token)):
            raise ValueError("client_token must contain 1..64 ASCII letters, digits, '_' or '-'")
        if aws_session is None:
            raise ValueError("Durable submission requires an explicit aws_session")
        if tags is not None and (not isinstance(tags, dict) or len(tags) > 50
                or any(not isinstance(k, str) or not 1 <= len(k) <= 128
                       or not isinstance(v, str) or len(v) > 256
                       for k, v in tags.items())):
            raise ValueError("tags must be a bounded string mapping")
        if kwargs:
            raise ValueError("Durable submission does not accept additional SDK options")
        if type(shots) is not int or shots <= 0:
            raise ValueError("Durable submission requires positive integer shots")
        region = device_arn.split(":")[3] if isinstance(device_arn, str) and device_arn.count(":") >= 5 else None
        if not region or aws_session.region != region:
            raise ValueError("Explicit session region must match the device ARN")
    circuit = _resolve_circuit(program_or_circuit)
    try:
        if client_token is not None:
            from braket.aws import AwsQuantumTask
            # create() serializes the circuit with the actual SDK. Its kwargs
            # are not used for the provider token; the session boundary is.
            task = AwsQuantumTask.create(
                _SubmissionSession(aws_session, client_token,
                                   expected_action if expected_action is not None
                                   else serialize_circuit_action(circuit)), device_arn,
                circuit, s3_folder, shots, tags=dict(tags) if tags is not None else None,
            )
            return task.id
        if expected_action is not None:
            raise ValueError("expected_action requires durable client_token")
        if tags is not None:
            kwargs["tags"] = tags
        device = AwsDevice(device_arn, **({'aws_session': aws_session} if aws_session is not None else {}))
        task = device.run(circuit, s3_folder, shots=shots, **kwargs)
        return task.id
    except Exception as exc:
        raise BraketDeviceError(
            f"Failed to submit circuit to device '{device_arn}': {exc}"
        ) from exc


def get_task_status(task_arn: str, *, aws_session: Any = None) -> str:
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
        task = AwsQuantumTask(task_arn, **({'aws_session': aws_session} if aws_session is not None else {}))
        return task.state()
    except Exception as exc:
        raise BraketDeviceError(
            f"Failed to retrieve status for task '{task_arn}': {exc}"
        ) from exc


def get_task_result(task_arn: str, *, aws_session: Any = None) -> BraketResult:
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
        task = AwsQuantumTask(task_arn, **({'aws_session': aws_session} if aws_session is not None else {}))
        return BraketResult(task.result())
    except Exception as exc:
        raise BraketDeviceError(
            f"Failed to retrieve result for task '{task_arn}': {exc}"
        ) from exc


def get_task_metadata(task_arn: str, *, aws_session: Any = None) -> dict[str, Any]:
    """Fetch fresh provider metadata by ARN for durable identity verification.

    Metadata is provider evidence, not a billing receipt. Braket does not
    guarantee that it returns the submission client token in task metadata.
    """
    from braket.aws import AwsQuantumTask
    try:
        task = AwsQuantumTask(task_arn, **({'aws_session': aws_session} if aws_session is not None else {}))
        return task.metadata(use_cached_value=False)
    except Exception as exc:
        raise BraketDeviceError("Failed to retrieve task metadata") from exc


def cancel_task(task_arn: str, *, aws_session: Any = None) -> None:
    """Request cancellation by persisted ARN; this does not prove cancellation.

    Poll the provider afterward. Acceptance, execution and charges can race
    cancellation, so callers must not release funds from this return alone.
    """
    from braket.aws import AwsQuantumTask
    try:
        task = AwsQuantumTask(task_arn, **({'aws_session': aws_session} if aws_session is not None else {}))
        task.cancel()
    except Exception as exc:
        raise BraketDeviceError("Failed to request task cancellation") from exc


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

    This is the primary entry point for the API layer (``rqm-api``).
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
    if backend == "local":
        translator = BraketTranslator(allow_local_u1q_unitary=True)
        circuit = translator.translate_descriptors(descriptors)
        return run_local(circuit, shots=shots)

    if backend == "device":
        translator = BraketTranslator()
        circuit = translator.translate_descriptors(descriptors)
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


def _resolve_circuit(
    program_or_circuit: Circuit | Any,
    *,
    allow_local_u1q_unitary: bool = False,
) -> Circuit:
    """Return a Braket ``Circuit`` from *program_or_circuit*.

    If the argument is already a ``Circuit``, it is returned unchanged.
    Otherwise it is translated via :class:`~rqm_braket.translator.BraketTranslator`.
    """
    if isinstance(program_or_circuit, Circuit):
        return program_or_circuit
    return BraketTranslator(
        allow_local_u1q_unitary=allow_local_u1q_unitary
    ).to_circuit(program_or_circuit)
