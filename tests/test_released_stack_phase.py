"""Offline exact-phase tests against the released core 0.3.1 contract."""

import math

import numpy as np
import pytest
from braket.circuits import Circuit

from rqm_braket.translator import BraketTranslator


@pytest.mark.parametrize("axis,gate", [(0, "rx"), (1, "ry"), (2, "rz")])
@pytest.mark.parametrize("angle", [2 * math.pi, -2 * math.pi, 4 * math.pi, 1e-10, -0.73])
def test_local_quaternion_matrix_preserves_exact_phase(axis, gate, angle):
    """This unitary escape hatch is local-only; no provider call is made."""
    components = [math.cos(angle / 2), 0.0, 0.0, 0.0]
    components[axis + 1] = math.sin(angle / 2)
    descriptor = {
        "gate": "u1q", "targets": [0], "controls": [],
        "params": dict(zip(("w", "x", "y", "z"), components)),
    }
    actual = BraketTranslator(allow_local_u1q_unitary=True).translate_descriptors([descriptor])
    expected = getattr(Circuit(), gate)(0, angle)
    np.testing.assert_allclose(actual.to_unitary(), expected.to_unitary(), atol=1e-12, rtol=0)
    # Raw arbitrary unitaries remain rejected on the hardware-facing path.
    with pytest.raises(ValueError):
        BraketTranslator().translate_descriptors([descriptor])
