"""
rqm_braket
==========

AWS Braket integration layer for the RQM ecosystem.

Public API
----------
RQMGate
    Typed dataclass descriptor for a single gate (alternative to plain dicts).

to_braket_circuit(gate_sequence, n_qubits=None)
    Translate an RQM gate-descriptor sequence into a Braket ``Circuit``.
    Accepts :class:`RQMGate` instances, plain ``dict`` descriptors, or a mix.

spinor_to_circuit(spinor, qubit=0)
    Translate a spinor [α, β] into a single-qubit state-prep circuit.

bloch_to_circuit(bloch_vector, qubit=0)
    Translate a Bloch vector [x, y, z] into a single-qubit state-prep circuit.

quaternion_to_circuit(quaternion, qubit=0)
    Translate a unit quaternion [w, x, y, z] into a single-qubit circuit.

run_local(circuit, shots=100)
    Execute a circuit on the local Braket state-vector simulator.

run_device(circuit, device_arn, s3_folder, shots=100, **kwargs)
    Execute a circuit on a remote AWS Braket device.

BraketResult
    Friendly wrapper around Braket task results.

Architecture note
-----------------
No canonical quaternion / spinor / Bloch / SU(2) math lives in this package.
All canonical math is delegated to ``rqm-core``.
"""

from rqm_braket.devices import run_device, run_local
from rqm_braket.results import BraketResult
from rqm_braket.translators import (
    RQMGate,
    bloch_to_circuit,
    quaternion_to_circuit,
    spinor_to_circuit,
    to_braket_circuit,
)

__all__ = [
    "RQMGate",
    "to_braket_circuit",
    "spinor_to_circuit",
    "bloch_to_circuit",
    "quaternion_to_circuit",
    "run_local",
    "run_device",
    "BraketResult",
]

__version__ = "0.1.0"
