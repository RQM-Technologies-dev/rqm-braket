"""Offline native-family codecs; these are not hardware qualification tests."""

from dataclasses import replace
import hashlib
import json

import pytest
from braket.ahs.analog_hamiltonian_simulation import AnalogHamiltonianSimulation
from braket.ahs.atom_arrangement import AtomArrangement
from braket.ahs.driving_field import DrivingField
from braket.timings.time_series import TimeSeries
from braket.circuits import Circuit, FreeParameter
from braket.ir.openqasm import Program
from braket.pulse import ConstantWaveform, Frame, Port, PulseSequence

from rqm_braket.workloads import decode_native_workload, export_native_workload


def test_gate_export_keeps_measurement_order_and_requires_bound_parameters():
    circuit = Circuit().h(0).cnot(0, 1).measure(1).measure(0)
    artifact = export_native_workload(circuit, family="gate_circuit")
    restored = decode_native_workload(artifact)
    assert restored.source.index("measure q[1]") < restored.source.index("measure q[0]")
    assert artifact.hardware_qualified is False
    assert "connectivity" in artifact.required_device_checks
    with pytest.raises(ValueError, match="Bind all"):
        export_native_workload(Circuit().rx(0, FreeParameter("theta")), family="gate_circuit")


def test_pulse_export_preserves_calibration_identifiers_and_capture():
    frame = Frame("synthetic_readout", Port("synthetic_port", 1e-9), 1e9, is_predefined=True)
    pulse = PulseSequence().play(frame, ConstantWaveform(1e-8, 0.1)).capture_v0(frame)
    artifact = export_native_workload(pulse, family="pulse_program")
    restored = decode_native_workload(artifact)
    assert restored.source == pulse.to_ir()
    assert "capture_v0" in restored.source and "synthetic_readout" in restored.source
    assert "calibrations" in artifact.required_device_checks
    assert artifact.hardware_qualified is False


def test_ahs_export_preserves_register_and_hamiltonian_without_discretizing():
    register = AtomArrangement().add((0, 0)).add((0, 5.123456789e-6))
    amplitude = TimeSeries().put(0, 0).put(1e-6, 1)
    zero = TimeSeries().put(0, 0).put(1e-6, 0)
    program = AnalogHamiltonianSimulation(register, DrivingField(amplitude, zero, zero))
    artifact = export_native_workload(program, family="analog_hamiltonian")
    assert decode_native_workload(artifact).dict() == program.to_ir().dict()
    assert "discretization" in artifact.required_device_checks
    assert artifact.hardware_qualified is False


def test_dynamic_export_keeps_control_and_intermediate_measurements_verbatim():
    source = "OPENQASM 3.0; bit b; qubit q; b = measure q; if (b == 1) { x q; } b = measure q;"
    artifact = export_native_workload(Program(source=source, inputs={}), family="dynamic_circuit")
    assert decode_native_workload(artifact).source == source
    assert "intermediate_measurements" in artifact.required_device_checks
    assert artifact.hardware_qualified is False


@pytest.mark.parametrize("family", ["pulse_program", "analog_hamiltonian", "dynamic_circuit", "unknown"])
def test_family_mismatch_cannot_reinterpret_gate_circuits(family):
    with pytest.raises(ValueError, match="family"):
        export_native_workload(Circuit().h(0), family=family)


@pytest.mark.parametrize("change", [
    {"family": "pulse_program"},
    {"action": "{}"},
    {"action_sha256": "a" * 64},
    {"schema_version": "future"},
])
def test_changed_native_artifact_is_rejected(change):
    artifact = export_native_workload(Circuit().h(0), family="gate_circuit")
    with pytest.raises(ValueError, match="binding"):
        decode_native_workload(replace(artifact, **change))


def test_unknown_native_fields_are_not_silently_discarded():
    artifact = export_native_workload(Program(source="OPENQASM 3.0;", inputs={}), family="dynamic_circuit")
    value = json.loads(artifact.action)
    value["unknown_control_semantics"] = {"meaning": "must not disappear"}
    action = json.dumps(value)
    changed = replace(
        artifact,
        action=action,
        action_sha256=hashlib.sha256(action.encode()).hexdigest(),
        workload_sha256=hashlib.sha256((artifact.schema_version + "\n" + artifact.family + "\n" + action).encode()).hexdigest(),
    )
    with pytest.raises(ValueError):
        decode_native_workload(changed)


def test_nonfinite_native_inputs_are_rejected():
    with pytest.raises(ValueError):
        export_native_workload(Program(source="OPENQASM 3.0;", inputs={"theta": float("nan")}), family="dynamic_circuit")
