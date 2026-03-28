"""
rqm_braket.api
==============

Flask Blueprint exposing rqm-braket execution and device-discovery functions
as REST API endpoints.

Mount this blueprint in your ``rqm-api`` Flask application to enable
end-to-end quantum job submission from RQM Studio:

.. code-block:: python

    from flask import Flask
    from rqm_braket.api import api_blueprint

    app = Flask(__name__)
    app.register_blueprint(api_blueprint, url_prefix="/v1")

Endpoints
---------
``POST /v1/run``
    Execute a circuit synchronously via :func:`~rqm_braket.execution.run_descriptors`.
    Supports both the ``"local"`` simulator and ``"device"`` backends.

``POST /v1/run/async``
    Submit a circuit to an AWS Braket device asynchronously via
    :func:`~rqm_braket.execution.run_device_async`.  Returns the task ARN
    immediately.

``GET /v1/tasks/<task_arn>/status``
    Query the live status of a submitted task via
    :func:`~rqm_braket.execution.get_task_status`.

``GET /v1/tasks/<task_arn>/result``
    Retrieve the result of a completed task via
    :func:`~rqm_braket.execution.get_task_result`.

``GET /v1/devices``
    List available AWS Braket devices via
    :func:`~rqm_braket.execution.list_devices`.

All endpoints return JSON.  Error responses use the following shape::

    {"error": "<message>"}

Requires
--------
flask >= 2.0

Install the optional ``[api]`` extra to pull in Flask:

.. code-block:: bash

    pip install rqm-braket[api]
"""

from __future__ import annotations

from importlib.util import find_spec

if find_spec("flask") is None:
    raise ImportError(
        "rqm_braket.api requires Flask. Install the optional dependency with 'pip install rqm-braket[api]'."
    )

from flask import Blueprint, Response, jsonify, request

from rqm_braket.execution import (
    BraketDeviceError,
    get_task_result,
    get_task_status,
    list_devices,
    run_descriptors,
    run_device_async,
)

api_blueprint = Blueprint("rqm_braket", __name__)


# ---------------------------------------------------------------------------
# POST /run  — synchronous execution
# ---------------------------------------------------------------------------


@api_blueprint.route("/run", methods=["POST"])
def run() -> tuple[Response, int]:
    """Execute a circuit synchronously and return the result.

    Request body (JSON)
    -------------------
    descriptors : list[dict]
        Ordered list of canonical gate descriptors.
    shots : int, optional
        Number of measurement shots (default 100).
    backend : str, optional
        ``"local"`` (default) or ``"device"``.
    device_arn : str, optional
        Required when *backend* is ``"device"``.
    s3_folder : list[str], optional
        ``[bucket, key_prefix]`` — required when *backend* is ``"device"``.

    Response body (JSON)
    --------------------
    counts : dict[str, int]
        Measurement outcome counts.
    shots : int
        Number of shots executed.
    probabilities : dict[str, float]
        Outcome probabilities.
    backend : str
        Always ``"braket"``.
    metadata : dict
        Task metadata (may be empty).
    """
    body = request.get_json(silent=True) or {}

    descriptors = body.get("descriptors")
    if not descriptors:
        return jsonify({"error": "'descriptors' is required and must be a non-empty list"}), 400

    shots: int = int(body.get("shots", 100))
    backend: str = str(body.get("backend", "local"))
    if backend not in ("local", "device"):
        return jsonify({"error": f"'backend' must be 'local' or 'device', got '{backend}'"}), 400

    device_arn: str | None = body.get("device_arn")
    s3_folder: tuple[str, str] | None = None
    s3_raw = body.get("s3_folder")
    if s3_raw is not None:
        if len(s3_raw) != 2:
            return jsonify({"error": "'s3_folder' must be a [bucket, key_prefix] list"}), 400
        s3_folder = (str(s3_raw[0]), str(s3_raw[1]))

    try:
        result = run_descriptors(
            descriptors,
            shots=shots,
            backend=backend,  # type: ignore[arg-type]
            device_arn=device_arn,
            s3_folder=s3_folder,
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except BraketDeviceError as exc:
        return jsonify({"error": str(exc)}), 502

    return jsonify(result.to_dict(include_probabilities=True)), 200


# ---------------------------------------------------------------------------
# POST /run/async  — asynchronous submission
# ---------------------------------------------------------------------------


@api_blueprint.route("/run/async", methods=["POST"])
def run_async() -> tuple[Response, int]:
    """Submit a circuit to an AWS Braket device and return the task ARN.

    Request body (JSON)
    -------------------
    descriptors : list[dict]
        Ordered list of canonical gate descriptors.
    shots : int, optional
        Number of measurement shots (default 100).
    device_arn : str
        ARN of the target AWS Braket device.
    s3_folder : list[str]
        ``[bucket, key_prefix]`` for Braket result storage.

    Response body (JSON)
    --------------------
    task_arn : str
        ARN of the submitted task.  Use with ``/tasks/<task_arn>/status``
        and ``/tasks/<task_arn>/result``.
    """
    body = request.get_json(silent=True) or {}

    descriptors = body.get("descriptors")
    if not descriptors:
        return jsonify({"error": "'descriptors' is required and must be a non-empty list"}), 400

    device_arn: str | None = body.get("device_arn")
    if not device_arn:
        return jsonify({"error": "'device_arn' is required for async execution"}), 400

    s3_raw = body.get("s3_folder")
    if not s3_raw or len(s3_raw) != 2:
        return jsonify({"error": "'s3_folder' must be a [bucket, key_prefix] list"}), 400
    s3_folder: tuple[str, str] = (str(s3_raw[0]), str(s3_raw[1]))

    shots: int = int(body.get("shots", 100))

    try:
        task_arn = run_device_async(descriptors, device_arn=device_arn, s3_folder=s3_folder, shots=shots)
    except BraketDeviceError as exc:
        return jsonify({"error": str(exc)}), 502

    return jsonify({"task_arn": task_arn}), 202


# ---------------------------------------------------------------------------
# GET /tasks/<task_arn>/status  — poll task state
# ---------------------------------------------------------------------------


@api_blueprint.route("/tasks/<path:task_arn>/status", methods=["GET"])
def task_status(task_arn: str) -> tuple[Response, int]:
    """Return the current status of an AWS Braket task.

    Path parameters
    ---------------
    task_arn : str
        ARN of the task (URL-encoded if it contains ``/``).

    Response body (JSON)
    --------------------
    task_arn : str
        Echo of the requested task ARN.
    status : str
        One of ``CREATED``, ``QUEUED``, ``RUNNING``, ``COMPLETED``,
        ``FAILED``, ``CANCELLED``.
    """
    try:
        status = get_task_status(task_arn)
    except BraketDeviceError as exc:
        return jsonify({"error": str(exc)}), 502

    return jsonify({"task_arn": task_arn, "status": status}), 200


# ---------------------------------------------------------------------------
# GET /tasks/<task_arn>/result  — retrieve completed task result
# ---------------------------------------------------------------------------


@api_blueprint.route("/tasks/<path:task_arn>/result", methods=["GET"])
def task_result(task_arn: str) -> tuple[Response, int]:
    """Retrieve the result of a completed AWS Braket task.

    Path parameters
    ---------------
    task_arn : str
        ARN of the task.

    Response body (JSON)
    --------------------
    counts : dict[str, int]
        Measurement outcome counts.
    shots : int
        Number of shots executed.
    probabilities : dict[str, float]
        Outcome probabilities.
    backend : str
        Always ``"braket"``.
    metadata : dict
        Task metadata (may be empty).
    task_id : str or None
        Task ARN extracted from metadata.
    """
    try:
        result = get_task_result(task_arn)
    except BraketDeviceError as exc:
        return jsonify({"error": str(exc)}), 502

    return jsonify(result.to_dict(include_probabilities=True, include_task_id=True)), 200


# ---------------------------------------------------------------------------
# GET /devices  — device discovery
# ---------------------------------------------------------------------------


@api_blueprint.route("/devices", methods=["GET"])
def devices() -> tuple[Response, int]:
    """List available AWS Braket devices.

    Query parameters
    ----------------
    type : str, optional
        Comma-separated device types to include, e.g. ``SIMULATOR`` or
        ``QPU,SIMULATOR``.  When omitted all types are returned.

    Response body (JSON)
    --------------------
    devices : list[dict]
        Each entry contains ``deviceArn``, ``deviceName``, ``deviceType``,
        ``status``, and ``providerName``.
    """
    type_param = request.args.get("type")
    device_types: list[str] | None = None
    if type_param:
        device_types = [t.strip().upper() for t in type_param.split(",") if t.strip()]

    try:
        device_list = list_devices(device_types=device_types)
    except BraketDeviceError as exc:
        return jsonify({"error": str(exc)}), 502

    return jsonify({"devices": device_list}), 200
