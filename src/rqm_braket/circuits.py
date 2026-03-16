"""
rqm_braket.circuits
===================

Lightweight helpers for constructing common demo circuits in Braket form.

No canonical math lives here.  These are simple, practical conveniences for
demonstration and testing.
"""

from __future__ import annotations

from braket.circuits import Circuit


def bell_circuit(qubit_a: int = 0, qubit_b: int = 1) -> Circuit:
    """Return a two-qubit Bell-state (maximally entangled) circuit.

    Applies ``H`` on ``qubit_a`` followed by ``CNOT(qubit_a, qubit_b)``,
    producing the :math:`|\\Phi^+\\rangle = (|00\\rangle + |11\\rangle)/\\sqrt{2}`
    Bell state.

    Parameters
    ----------
    qubit_a:
        Index of the first qubit (default 0).
    qubit_b:
        Index of the second qubit (default 1).

    Returns
    -------
    braket.circuits.Circuit

    Examples
    --------
    >>> from rqm_braket.circuits import bell_circuit
    >>> circuit = bell_circuit()
    >>> print(circuit)
    """
    circuit = Circuit()
    circuit.h(qubit_a)
    circuit.cnot(qubit_a, qubit_b)
    return circuit


def ghz_circuit(n_qubits: int = 3) -> Circuit:
    """Return an *n*-qubit GHZ circuit.

    Applies ``H`` on qubit 0, then ``CNOT(0, k)`` for ``k = 1..n_qubits-1``,
    producing the :math:`(|00\\ldots0\\rangle + |11\\ldots1\\rangle)/\\sqrt{2}`
    GHZ state.

    Parameters
    ----------
    n_qubits:
        Total number of qubits (must be ≥ 2).

    Returns
    -------
    braket.circuits.Circuit

    Raises
    ------
    ValueError
        If ``n_qubits < 2``.

    Examples
    --------
    >>> from rqm_braket.circuits import ghz_circuit
    >>> circuit = ghz_circuit(3)
    >>> print(circuit)
    """
    if n_qubits < 2:
        raise ValueError(f"GHZ circuit requires at least 2 qubits, got {n_qubits}.")
    circuit = Circuit()
    circuit.h(0)
    for k in range(1, n_qubits):
        circuit.cnot(0, k)
    return circuit


def single_qubit_demo_circuit(qubit: int = 0) -> Circuit:
    """Return a simple single-qubit demo circuit: ``H → S → T``.

    Parameters
    ----------
    qubit:
        Target qubit index (default 0).

    Returns
    -------
    braket.circuits.Circuit

    Examples
    --------
    >>> from rqm_braket.circuits import single_qubit_demo_circuit
    >>> circuit = single_qubit_demo_circuit()
    >>> print(circuit)
    """
    circuit = Circuit()
    circuit.h(qubit)
    circuit.s(qubit)
    circuit.t(qubit)
    return circuit
