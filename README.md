# rqm-braket

Amazon Braket backend bridge for the **RQM ecosystem**.

## What is rqm-braket?

`rqm-braket` is a **thin adapter layer** that connects [`rqm-core`](https://github.com/RQM-Technologies-dev/rqm-core) objects to the [Amazon Braket](https://aws.amazon.com/braket/) quantum computing service.

> **No canonical math lives here.**
> This repo adapts `rqm-core` objects to Amazon Braket.
> Quaternion math, spinor math, Bloch math, and SU(2) math all live in `rqm-core`.

---

## Architecture

```
  rqm-docs / rqm-notebooks
          ↑
   rqm-core   rqm-qiskit   rqm-braket
```

| Layer | Role |
|---|---|
| `rqm-core` | Canonical quaternion / spinor / SU(2) math |
| `rqm-braket` | Translators → Braket circuits, result wrappers, device helpers |
| `rqm-qiskit` | Analogous adapter for Qiskit |

---

## Installation

```bash
pip install rqm-braket
```

To install from source:

```bash
git clone https://github.com/RQM-Technologies-dev/rqm-braket
cd rqm-braket
pip install -e ".[dev]"
```

---

## Quick Start

### Run a Bell state locally

```python
from rqm_braket import to_braket_circuit, run_local, BraketResult
from rqm_braket.circuits import bell_circuit

circuit = bell_circuit()
result = run_local(circuit, shots=100)
print(result.counts)
print(result.probabilities)
```

### Translate an RQM gate sequence

```python
from rqm_braket import to_braket_circuit

gate_sequence = [
    {"gate": "H", "target": 0},
    {"gate": "CNOT", "control": 0, "target": 1},
]
circuit = to_braket_circuit(gate_sequence, n_qubits=2)
print(circuit)
```

### Run on an AWS device

```python
from rqm_braket import run_device
from rqm_braket.circuits import bell_circuit

circuit = bell_circuit()
result = run_device(
    circuit,
    device_arn="arn:aws:braket:::device/quantum-simulator/amazon/sv1",
    s3_folder=("my-bucket", "my-prefix"),
    shots=100,
)
print(result.counts)
```

---

## Public API

| Symbol | Description |
|---|---|
| `to_braket_circuit(gate_sequence, n_qubits)` | Translate an RQM gate sequence to a Braket `Circuit` |
| `run_local(circuit, shots)` | Execute on the local Braket simulator |
| `run_device(circuit, device_arn, s3_folder, shots)` | Execute on an AWS Braket device |
| `BraketResult` | Friendly wrapper around Braket task results |

---

## Development & Testing

```bash
pip install -e ".[dev]"
pytest
```

Tests are designed to run **offline** using the Braket local simulator.
Cloud execution paths are mocked and do not require AWS credentials.

---

## Contributing

- Do **not** implement canonical quaternion / spinor / Bloch / SU(2) math here.
- Import and delegate to `rqm-core`.
- Keep Braket-specific code limited to translation, execution, and result normalization.
- See `AGENTS.md` for full contribution rules.