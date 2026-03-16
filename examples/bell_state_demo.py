"""
bell_state_demo.py
==================

Demonstrates how to create a Bell-state circuit and run it on the local
Braket simulator, then inspect the results via ``BraketResult``.

A Bell state is the maximally entangled two-qubit state:

    |Φ+⟩ = (|00⟩ + |11⟩) / √2

For 100 shots we expect roughly half '00' and half '11' outcomes,
with no '01' or '10' outcomes (up to simulation noise).
"""

from rqm_braket.circuits import bell_circuit
from rqm_braket.devices import run_local


def main() -> None:
    # Create the Bell-state circuit
    circuit = bell_circuit(qubit_a=0, qubit_b=1)
    print("Bell-state circuit:")
    print(circuit)

    # Run on the local simulator
    result = run_local(circuit, shots=100)

    print("\nMeasurement counts:")
    for outcome, count in sorted(result.counts.items()):
        bar = "█" * count
        print(f"  |{outcome}⟩: {count:3d}  {bar}")

    print("\nEmpirical probabilities:")
    for outcome, prob in sorted(result.probabilities.items()):
        print(f"  |{outcome}⟩: {prob:.3f}")

    print(f"\nTotal shots : {result.shots}")
    print(f"BraketResult: {result!r}")


if __name__ == "__main__":
    main()
