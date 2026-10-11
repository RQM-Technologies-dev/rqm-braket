"""Synthetic SDK results, never hardware or billing evidence."""

import numpy as np
import pytest
from braket.task_result import TaskMetadata
from braket.tasks import AnalogHamiltonianSimulationQuantumTaskResult
from braket.tasks.analog_hamiltonian_simulation_quantum_task_result import (
    AnalogHamiltonianSimulationShotStatus as Status,
    ShotResult,
)

from rqm_braket.ahs_results import normalize_ahs_result

TASK = "arn:aws:braket:us-east-1:000000000000:quantum-task/00000000-0000-4000-8000-000000000001"
DEVICE = "arn:aws:braket:us-east-1::device/qpu/quera/Aquila"


def result():
    return AnalogHamiltonianSimulationQuantumTaskResult(
        task_metadata=TaskMetadata(id=TASK, shots=4, deviceId=DEVICE),
        additional_metadata=None,
        measurements=[
            ShotResult(Status.SUCCESS, np.array([1, 1]), np.array([0, 1])),
            ShotResult(Status.SUCCESS, np.array([0, 1]), np.array([0, 0])),
            ShotResult(Status.PARTIAL_SUCCESS, np.array([1, 0]), None),
            ShotResult(Status.FAILURE, None, None),
        ],
    )


def adapt(raw, **changes):
    expected = dict(expected_task_arn=TASK, expected_device_arn=DEVICE, expected_shots=4, expected_sites=2)
    return normalize_ahs_result(raw, **{**expected, **changes})


def test_failed_and_partial_shots_remain_visible_without_binary_reinterpretation():
    data = adapt(result())
    assert data["successful_state_counts"] == {"rg": 1, "er": 1}
    assert data["shot_status_counts"] == {"Success": 2, "Partial Success": 1, "Failure": 1}
    assert len(data["measurements"]) == 4
    assert data["measurements"][2]["post_sequence"] is None
    assert data["site_order"] == "submitted_register_order"


@pytest.mark.parametrize("changes", [
    {"expected_task_arn": "another-task"},
    {"expected_device_arn": "another-device"},
    {"expected_shots": 3},
    {"expected_shots": True},
    {"expected_sites": 3},
])
def test_result_binding_mismatches_fail(changes):
    with pytest.raises(ValueError):
        adapt(result(), **changes)


@pytest.mark.parametrize("bad", [None, np.array([1]), np.array([1, 2]), np.array([1.0, 0.0])])
def test_successful_shot_requires_complete_binary_site_sequences(bad):
    raw = result()
    raw.measurements[0].post_sequence = bad
    with pytest.raises(ValueError):
        adapt(raw)
