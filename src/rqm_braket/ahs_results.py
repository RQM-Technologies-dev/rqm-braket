"""AHS result adaptation that retains unsuccessful shots and site order."""

from __future__ import annotations

from numbers import Integral
from collections.abc import Iterable
from typing import Any

from braket.tasks import AnalogHamiltonianSimulationQuantumTaskResult
from braket.tasks.analog_hamiltonian_simulation_quantum_task_result import (
    AnalogHamiltonianSimulationShotStatus,
)


def normalize_ahs_result(
    raw: AnalogHamiltonianSimulationQuantumTaskResult,
    *,
    expected_task_arn: str,
    expected_device_arn: str,
    expected_shots: int,
    expected_sites: int,
) -> dict[str, Any]:
    """Validate expected task/device/shape and preserve every AHS shot outcome.

    State counts use the SDK's e/r/g convention and contain successful shots
    only. Partial and failed shots remain in the returned per-shot records;
    they are not silently replaced, retried, or treated as refunds. Accounting
    and physical qualification remain the hosting platform's responsibility.
    """
    if (
        type(raw) is not AnalogHamiltonianSimulationQuantumTaskResult
        or type(expected_shots) is not int or expected_shots <= 0
        or type(expected_sites) is not int or expected_sites <= 0
        or raw.task_metadata.id != expected_task_arn
        or raw.task_metadata.deviceId != expected_device_arn
        or raw.task_metadata.shots != expected_shots
        or raw.measurements is None
        or len(raw.measurements) != expected_shots
    ):
        raise ValueError("AHS result identity or shot count mismatch")

    def sequence(value: Iterable[Integral] | None) -> list[int] | None:
        if value is None:
            return None
        items = list(value)
        if len(items) != expected_sites or any(
            isinstance(item, bool) or not isinstance(item, Integral) or item not in (0, 1)
            for item in items
        ):
            raise ValueError("AHS result site sequence is malformed")
        return [int(item) for item in items]

    records = []
    totals = {status.value: 0 for status in AnalogHamiltonianSimulationShotStatus}
    for shot in raw.measurements:
        if not isinstance(shot.status, AnalogHamiltonianSimulationShotStatus):
            raise ValueError("Unknown AHS shot status")
        pre, post = sequence(shot.pre_sequence), sequence(shot.post_sequence)
        if shot.status == AnalogHamiltonianSimulationShotStatus.SUCCESS and (pre is None or post is None):
            raise ValueError("Successful AHS shot is missing measurements")
        totals[shot.status.value] += 1
        records.append({"status": shot.status.value, "pre_sequence": pre, "post_sequence": post})
    return {
        "schema_version": "rqm.braket.ahs-result.v1",
        "provider_task_arn": expected_task_arn,
        "device_arn": expected_device_arn,
        "shots": expected_shots,
        "sites": expected_sites,
        "site_order": "submitted_register_order",
        "state_alphabet": {"e": "empty", "r": "rydberg", "g": "ground"},
        "successful_state_counts": raw.get_counts(),
        "shot_status_counts": totals,
        "measurements": records,
    }
