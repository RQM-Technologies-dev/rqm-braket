"""
rqm_braket
==========

Amazon Braket backend bridge for the RQM ecosystem.

Public API
----------
to_braket_circuit(gate_sequence, n_qubits=None)
    Translate an RQM gate-descriptor sequence into a Braket ``Circuit``.

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
from rqm_braket.translators import to_braket_circuit

__all__ = [
    "to_braket_circuit",
    "run_local",
    "run_device",
    "BraketResult",
]

__version__ = "0.1.0"
