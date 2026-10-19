"""AQT native descriptors and actual SDK requests, with inert transport only."""

import json
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pytest
from braket.circuits import Circuit
from rqm_braket.execution import (
    AQT_IBEX_DEVICE_PARAMETERS_CONTRACT_VERSION,
    BraketDeviceError,
    run_device_async,
    serialize_circuit_action,
)
from rqm_braket.translator import BraketTranslator

IBEX = "arn:aws:braket:eu-north-1::device/qpu/aqt/Ibex-Q1"
TASK = "arn:aws:braket:eu-north-1:075992502426:quantum-task/offline"


def op(gate, targets, **params):
    return {"gate": gate, "targets": targets, "controls": [], "params": params}


@pytest.mark.parametrize("angle,phase", [(0, 0), (-0.73, 1.2), (1.4, -2.1)])
def test_native_descriptor_sdk_parity_and_terminal_measurement_order(angle, phase):
    descriptors = [
        op("prx", [2], angle=angle, phase=phase),
        op("xx", [2, 0], angle=-0.41),
        op("rz", [0], angle=0.2),
        op("measure", [2, 0]),
    ]
    circuit = BraketTranslator().translate_descriptors(descriptors)
    expected = Circuit().prx(2, angle, phase).xx(2, 0, -0.41).rz(0, 0.2).measure([2, 0])
    assert serialize_circuit_action(circuit) == serialize_circuit_action(expected)
    assert np.allclose(
        BraketTranslator().translate_descriptors(descriptors[:-1]).to_unitary(),
        Circuit().prx(2, angle, phase).xx(2, 0, -0.41).rz(0, 0.2).to_unitary(),
    )


@pytest.mark.parametrize(
    "patch",
    [
        {"targets": []},
        {"targets": [0, 1]},
        {"targets": [True]},
        {"targets": [-1]},
        {"targets": ["0"]},
        {"controls": [1]},
        {"params": {"angle": 1}},
        {"params": {"angle": 1, "phase": 2, "extra": 3}},
        *[
            {"params": {"angle": 1, "phase": value}}
            for value in [True, "0.2", None, float("nan"), float("inf"), 10**1000]
        ],
        *[
            {"params": {"angle": value, "phase": 1}}
            for value in [False, "0.2", None, float("nan"), float("-inf"), 10**1000]
        ],
    ],
)
def test_bad_prx_rejected_before_sdk_construction(patch):
    descriptor = {**op("prx", [0], angle=1, phase=2), **deepcopy(patch)}
    factory = Mock(side_effect=AssertionError("SDK circuit constructed"))
    with pytest.raises((ValueError, TypeError)):
        BraketTranslator().translate_descriptors([descriptor], circuit_factory=factory)
    factory.assert_not_called()


def test_ibex_real_sdk_uses_advertised_common_schema_and_frozen_native_action():
    assert AQT_IBEX_DEVICE_PARAMETERS_CONTRACT_VERSION == 1
    circuit = Circuit().prx(0, -0.2, 0.3).xx(0, 1, 0.4).rz(1, 0.5).measure([1, 0])
    frozen = serialize_circuit_action(circuit)
    session = SimpleNamespace(
        region="eu-north-1", create_quantum_task=Mock(return_value=TASK)
    )
    assert (
        run_device_async(
            circuit,
            IBEX,
            ("offline-bucket", "rqm-hardware-v1"),
            100,
            aws_session=session,
            client_token="saved-token",
            expected_action=frozen,
        )
        == TASK
    )
    request = session.create_quantum_task.call_args.kwargs
    assert request["deviceArn"] == IBEX
    assert request["action"] == frozen
    assert request["clientToken"] == "saved-token" and request["shots"] == 100
    assert request["outputS3Bucket"] == "offline-bucket"
    assert request["outputS3KeyPrefix"] == "rqm-hardware-v1"
    assert (
        request.get("tags") is None
    )  # Retained regional policy requires untagged creates.
    parameters = json.loads(request["deviceParameters"])
    assert parameters["braketSchemaHeader"] == {
        "name": "braket.device_schema.common.gate_model_device_parameters",
        "version": "1",
    }
    assert parameters["paradigmParameters"]["qubitCount"] == 2
    assert parameters["paradigmParameters"]["disableQubitRewiring"] is False
    session.create_quantum_task.assert_called_once()


def test_ibex_wrong_region_or_frozen_action_cannot_dispatch():
    session = SimpleNamespace(region="us-west-1", create_quantum_task=Mock())
    with pytest.raises(ValueError, match="region"):
        run_device_async(
            Circuit().prx(0, 1, 2),
            IBEX,
            ("bucket", "prefix"),
            100,
            aws_session=session,
            client_token="saved-token",
        )
    session.region = "eu-north-1"
    with pytest.raises(BraketDeviceError):
        run_device_async(
            Circuit().prx(0, 1, 2),
            IBEX,
            ("bucket", "prefix"),
            100,
            aws_session=session,
            client_token="saved-token",
            expected_action="changed",
        )
    session.create_quantum_task.assert_not_called()
