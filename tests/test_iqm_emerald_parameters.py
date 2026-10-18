"""Exercise the real SDK serializer with fake transport; no AWS access."""
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from braket.circuits import Circuit

from rqm_braket.execution import (
    IQM_EMERALD_DEVICE_PARAMETERS_CONTRACT_VERSION,
    IQM_GARNET_DEVICE_PARAMETERS_CONTRACT_VERSION,
    run_device_async,
    serialize_circuit_action,
)


@pytest.mark.parametrize("device", ["Emerald", "Garnet"])
def test_iqm_exact_devices_preserve_schema_virtual_wires_and_token(device):
    assert IQM_EMERALD_DEVICE_PARAMETERS_CONTRACT_VERSION == IQM_GARNET_DEVICE_PARAMETERS_CONTRACT_VERSION == 1
    circuit = Circuit().h(0).cnot(0, 1).measure([1, 0])
    action = serialize_circuit_action(circuit)
    arn = f"arn:aws:braket:eu-north-1::device/qpu/iqm/{device}"
    task = "arn:aws:braket:eu-north-1:075992502426:quantum-task/offline"
    session = SimpleNamespace(region="eu-north-1", create_quantum_task=Mock(return_value=task))
    assert run_device_async(circuit, arn, ("offline-bucket", "rqm-hardware-v1"), shots=100, aws_session=session, client_token="persisted-token", expected_action=action) == task
    request = session.create_quantum_task.call_args.kwargs
    assert request["deviceArn"] == arn and request["clientToken"] == "persisted-token"
    assert request["action"] == action and request["shots"] == 100
    params = json.loads(request["deviceParameters"])
    assert params["braketSchemaHeader"]["name"] == "braket.device_schema.iqm.iqm_device_parameters"
    assert params["paradigmParameters"]["disableQubitRewiring"] is False
    assert params["paradigmParameters"]["qubitCount"] == 2
    session.create_quantum_task.assert_called_once()
