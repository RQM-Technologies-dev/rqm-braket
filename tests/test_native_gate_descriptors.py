"""Native SDK mapping and rejection tests; no device or AWS session is created."""

from copy import deepcopy

import numpy as np
import pytest
from braket.circuits import Circuit

from rqm_braket.translator import BraketTranslator


@pytest.mark.parametrize("gate", [
    "xy", "pswap", "cphaseshift", "cphaseshift00", "cphaseshift01", "cphaseshift10", "cswap",
])
def test_native_gate_preserves_control_target_order_and_sdk_action(gate):
    targets = [2, 0] if gate in {"xy", "pswap", "cswap"} else [0]
    controls = [1] if gate.startswith("c") else []
    params = {} if gate == "cswap" else {"angle": -0.731}
    descriptor = {"gate": gate, "targets": targets, "controls": controls, "params": params}
    result = BraketTranslator().translate_descriptors([descriptor])
    args = controls + targets + ([] if gate == "cswap" else [-0.731])
    expected = getattr(Circuit(), gate)(*args)
    assert result.to_ir().json() == expected.to_ir().json()
    assert np.allclose(result.to_unitary(), expected.to_unitary(), atol=1e-12, rtol=0)


@pytest.mark.parametrize("gate", ["xy", "pswap", "cphaseshift00", "cswap"])
@pytest.mark.parametrize("mutation", ["boolean_wire", "duplicate_wire", "wrong_controls", "extra_param", "nan_angle"])
def test_malformed_native_gates_reject_before_sdk_call(gate, mutation):
    descriptor = {
        "gate": gate,
        "targets": [0, 2] if gate in {"xy", "pswap", "cswap"} else [0],
        "controls": [1] if gate.startswith("c") else [],
        "params": {} if gate == "cswap" else {"angle": 0.7},
    }
    bad = deepcopy(descriptor)
    if mutation == "boolean_wire":
        bad["targets"][0] = True
    elif mutation == "duplicate_wire":
        bad["targets"].append(bad["targets"][0])
    elif mutation == "wrong_controls":
        bad["controls"] = [3, 4]
    elif mutation == "extra_param":
        bad["params"]["unrecognized"] = 1
    else:
        bad["params"]["angle"] = float("nan")

    def must_not_construct():
        pytest.fail("constructed SDK circuit before validation")

    with pytest.raises((TypeError, ValueError)):
        BraketTranslator().translate_descriptors([bad], circuit_factory=must_not_construct)
