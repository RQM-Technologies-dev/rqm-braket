"""
basic_local_simulator.py
========================

Demonstrates how to build a simple circuit and run it on the local
Braket state-vector simulator — no AWS credentials required.
"""

from rqm_braket.circuits import single_qubit_demo_circuit
from rqm_braket.devices import run_local


def main() -> None:
    # Build a simple single-qubit demo circuit (H → S → T)
    circuit = single_qubit_demo_circuit(qubit=0)
    print("Circuit:")
    print(circuit)

    # Run on the local simulator
    result = run_local(circuit, shots=200)

    print("\nMeasurement counts:")
    for outcome, count in sorted(result.counts.items()):
        print(f"  |{outcome}⟩: {count}")

    print("\nProbabilities:")
    for outcome, prob in sorted(result.probabilities.items()):
        print(f"  |{outcome}⟩: {prob:.3f}")

    print(f"\nTotal shots: {result.shots}")


if __name__ == "__main__":
    main()
