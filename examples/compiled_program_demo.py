"""
compiled_program_demo.py
========================

Demonstrates the new compiler-boundary API introduced in ``rqm-braket`` v0.2.

Rather than supplying raw ``dict`` gate descriptors, callers now work with
:class:`~rqm_braket.translator.RQMGate` typed instructions — or any object
whose ``gate``, ``target``, ``control``, and ``angle`` attributes match the
``CompiledInstruction`` structural protocol.

When ``rqm-compiler`` is available its ``CompiledProgram`` objects can be
passed directly to :func:`~rqm_braket.translator.compile_to_braket_circuit`,
:func:`~rqm_braket.execution.run_local`, or
:class:`~rqm_braket.backend.BraketBackend`.

No AWS credentials are required to run this example.
"""

import math

from rqm_braket import BraketBackend, BraketResult, RQMGate, compile_to_braket_circuit
from rqm_braket.execution import run_local


# ---------------------------------------------------------------------------
# 1.  Build a Bell-state program using RQMGate
# ---------------------------------------------------------------------------

bell_program = [
    RQMGate(gate="H", target=0),
    RQMGate(gate="CNOT", target=1, control=0),
]

print("=== Bell-state program (RQMGate sequence) ===")
for instr in bell_program:
    print(f"  {instr}")


# ---------------------------------------------------------------------------
# 2.  Translate directly to a Braket Circuit
# ---------------------------------------------------------------------------

circuit = compile_to_braket_circuit(bell_program)
print("\nBraket circuit:")
print(circuit)


# ---------------------------------------------------------------------------
# 3.  Execute on the local simulator via the module-level helper
# ---------------------------------------------------------------------------

result: BraketResult = run_local(bell_program, shots=200)
print("\nMeasurement counts (run_local, 200 shots):")
for outcome, count in sorted(result.counts.items()):
    bar = "█" * (count // 5)
    print(f"  |{outcome}⟩: {count:3d}  {bar}")

print(f"\nMost likely bitstring: |{result.most_likely_bitstring()}⟩")
print(f"Total shots         : {result.shots}")


# ---------------------------------------------------------------------------
# 4.  Execute via BraketBackend — the unified backend object
# ---------------------------------------------------------------------------

backend = BraketBackend()

# Translate only
circuit2 = backend.compile_to_circuit(bell_program)
assert circuit2.qubit_count == 2

# Run
result2 = backend.run_local(bell_program, shots=100)
print("\nMeasurement counts (BraketBackend, 100 shots):")
for outcome, count in sorted(result2.counts.items()):
    print(f"  |{outcome}⟩: {count}")


# ---------------------------------------------------------------------------
# 5.  Simulate passing a rqm-compiler CompiledProgram
#     (mimicked here with a minimal stub that satisfies the protocol)
# ---------------------------------------------------------------------------


class _SimulatedCompiledProgram:
    """Stub that mimics the CompiledProgram protocol from rqm-compiler."""

    def __init__(self) -> None:
        self.instructions = [
            RQMGate(gate="H", target=0),
            RQMGate(gate="RX", target=0, angle=math.pi / 4),
            RQMGate(gate="CNOT", target=1, control=0),
            RQMGate(gate="RZ", target=1, angle=math.pi / 2),
        ]


compiled = _SimulatedCompiledProgram()
result3 = backend.run_local(compiled, shots=100)
print("\nCompiledProgram-style input result (100 shots):")
for outcome, count in sorted(result3.counts.items()):
    print(f"  |{outcome}⟩: {count}")

print("\nAll assertions passed — compiled_program_demo complete.")
