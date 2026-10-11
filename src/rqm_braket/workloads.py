"""Versioned native workload exports, without admission or provider calls.

These codecs validate SDK types and serialization. They do not establish device
compatibility, physical qualification, pricing, or permission to execute. In
particular, preserving a dynamic OpenQASM program is not a claim that a selected
QPU supports it. No terminal-measurement conversion is performed here.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Literal

from braket.ahs.analog_hamiltonian_simulation import AnalogHamiltonianSimulation
from braket.circuits import Circuit
from braket.ir.ahs import Program as AhsProgram
from braket.ir.openqasm import Program as OpenQasmProgram
from braket.pulse import PulseSequence

from rqm_braket.execution import serialize_circuit_action

WorkloadFamily = Literal["gate_circuit", "pulse_program", "analog_hamiltonian", "dynamic_circuit"]
VERSION = "rqm.braket.native-workload.v1"
MAX_ACTION_BYTES = 1_048_576
_FAMILIES = {"gate_circuit", "pulse_program", "analog_hamiltonian", "dynamic_circuit"}


def _binding(family: str, action: str) -> str:
    return hashlib.sha256((VERSION + "\n" + family + "\n" + action).encode("utf-8")).hexdigest()


def _reject_constant(value: str) -> None:
    raise ValueError("Native action contains a non-finite number")


@dataclass(frozen=True)
class NativeWorkload:
    """Immutable SDK action bytes plus an explicitly unqualified workload family.

    The binding is SHA-256 of UTF-8 ``version + LF + family + LF + action``.
    Neither action bytes nor floating-point values are reserialized for hashing.
    A caller must bind this export to device evidence, shots, terms and approval
    before any execution. This object is not accepted by the existing run helpers.
    """

    family: WorkloadFamily
    action: str
    action_sha256: str
    workload_sha256: str
    schema_version: str = VERSION

    @property
    def hardware_qualified(self) -> bool:
        """Serialization never constitutes physical qualification."""
        return False

    @property
    def required_device_checks(self) -> tuple[str, ...]:
        """Validation still required by a device-specific execution adapter."""
        common = ("physical_location", "live_capability_snapshot", "shots", "pricing_and_accounting")
        extra = {
            "gate_circuit": ("operations", "connectivity", "measurement_mapping"),
            "pulse_program": ("frames", "calibrations", "waveforms", "pulse_timing", "capture_mapping"),
            "analog_hamiltonian": ("lattice", "hamiltonian_ranges", "time_series", "discretization"),
            "dynamic_circuit": ("classical_control", "intermediate_measurements", "result_registers"),
        }
        return common + extra[self.family]


def decode_native_workload(workload: NativeWorkload) -> OpenQasmProgram | AhsProgram:
    """Check immutable bindings and SDK schema without changing native semantics.

    This is a codec, not a device validator. Dynamic control, pulse frames and
    analog Hamiltonians remain in their native representation; they are never
    passed through the terminal gate-circuit translator.
    """
    if (
        type(workload) is not NativeWorkload
        or workload.schema_version != VERSION
        or not isinstance(workload.family, str)
        or workload.family not in _FAMILIES
        or not isinstance(workload.action, str)
        or not 0 < len(workload.action.encode("utf-8")) <= MAX_ACTION_BYTES
        or hashlib.sha256(workload.action.encode("utf-8")).hexdigest() != workload.action_sha256
        or _binding(workload.family, workload.action) != workload.workload_sha256
    ):
        raise ValueError("Native workload binding mismatch")
    value = json.loads(workload.action, parse_constant=_reject_constant)
    # Also catches overflowed JSON numbers such as 1e999.
    json.dumps(value, allow_nan=False)
    expected = "braket.ir.ahs.program" if workload.family == "analog_hamiltonian" else "braket.ir.openqasm.program"
    header = value.get("braketSchemaHeader") if isinstance(value, dict) else None
    if not isinstance(header, dict) or header.get("name") != expected:
        raise ValueError("Native workload schema does not match its family")
    model = AhsProgram if workload.family == "analog_hamiltonian" else OpenQasmProgram
    decoded = model.parse_raw(workload.action)
    if json.loads(decoded.json()) != value:
        raise ValueError("Native workload has unsupported or noncanonical schema fields")
    return decoded


def export_native_workload(
    program: Circuit | PulseSequence | AnalogHamiltonianSimulation | OpenQasmProgram,
    *,
    family: WorkloadFamily,
) -> NativeWorkload:
    """Serialize one explicitly selected SDK workload family, without AWS access.

    Gate and pulse parameters must already be bound. Dynamic OpenQASM is kept
    verbatim and remains semantically unvalidated. AHS discretization must be an
    explicit upstream transformation, never a silent action during submission.
    All exports remain unqualified until the hosting platform validates the
    selected device, result adapter, permissions and accounting.
    """
    types = {
        "gate_circuit": Circuit,
        "pulse_program": PulseSequence,
        "analog_hamiltonian": AnalogHamiltonianSimulation,
        "dynamic_circuit": OpenQasmProgram,
    }
    if not isinstance(family, str) or family not in types or type(program) is not types[family]:
        raise ValueError("Explicit workload family does not match the SDK program")
    if isinstance(program, (Circuit, PulseSequence)) and program.parameters:
        raise ValueError("Bind all workload parameters before freezing")
    if isinstance(program, Circuit):
        action = serialize_circuit_action(program)
    elif isinstance(program, PulseSequence):
        action = OpenQasmProgram(source=program.to_ir(), inputs={}).json()
    elif isinstance(program, AnalogHamiltonianSimulation):
        action = program.to_ir().json()
    else:
        action = program.json()
    result = NativeWorkload(
        family=family,
        action=action,
        action_sha256=hashlib.sha256(action.encode("utf-8")).hexdigest(),
        workload_sha256=_binding(family, action),
    )
    decode_native_workload(result)
    return result
