# rqm-braket

AWS Braket integration layer for the **Resonant Quantum Mechanics (RQM)** ecosystem.

This package translates **RQM objects and operations** into **Amazon Braket circuits** and provides helpers for running those circuits on both:

- the **Braket Local Simulator**
- **AWS Braket quantum devices**

`rqm-braket` is a **backend bridge**, not a math engine.

All canonical quaternion, spinor, Bloch, and SU(2) mathematics live in **`rqm-core`**.

---

## Position in the RQM Ecosystem

The RQM software stack separates **canonical mathematics** from **execution backends**.

```
                ┌──────────────────┐
                │    rqm-docs      │
                │  documentation   │
                └────────┬─────────┘
                         │
       ┌─────────────────┼─────────────────┐
       │                 │                 │
┌──────┴──────┐          │      ┌──────────┴─────────┐
│  rqm-core   │          │      │     rqm-qiskit     │
│ canonical   │          │      │   Qiskit bridge    │
│    math     │          │      │                    │
└──────┬──────┘          │      └──────────┬─────────┘
       │                 │                 │
       │          ┌──────┴──────┐          │
       │          │ rqm-braket  │          │
       │          │ AWS Braket  │          │
       │          │   bridge    │          │
       │          └──────┬──────┘          │
       │                 │                 │
       └─────────────────┼─────────────────┘
                         │
                ┌────────┴─────────┐
                │  rqm-notebooks   │
                │ tutorials / demos│
                └──────────────────┘
```

---

## What This Package Provides

`rqm-braket` contains three main components:

### 1️⃣ Translators

Convert RQM-side objects into **Amazon Braket circuits**.

Examples:

- spinor → Braket circuit
- Bloch vector → Braket circuit
- quaternion rotation → Braket circuit

These translators **delegate all math to `rqm-core`**.

---

### 2️⃣ Result Wrappers

Provide simple Python-friendly access to Braket outputs.

Examples:

- measurement counts
- probability helpers
- convenience methods like:

```python
result.most_likely_bitstring()
result.probability_of("00")
```

---

### 3️⃣ Device Execution Helpers

Run circuits on:

- Braket **LocalSimulator**
- AWS **Braket devices**

Helpers simplify the normal Braket task workflow.

---

## Installation

```bash
pip install rqm-braket
```

Development install:

```bash
pip install -e .
```

---

## Quick Example

```python
from rqm_braket.devices import run_local
from rqm_braket.translators import spinor_to_circuit

# |+⟩ state: equal superposition of |0⟩ and |1⟩
spinor = [1, 1]

circuit = spinor_to_circuit(spinor)

result = run_local(circuit, shots=1000)

print(result.counts)
print(result.most_likely_bitstring())
```

---

## Examples

Example scripts are provided in the `examples/` directory.

### Local simulator demo

```
examples/basic_local_simulator.py
```

Creates a simple circuit and runs it on the Braket Local Simulator.

### Bell state demo

```
examples/bell_state_demo.py
```

Constructs a Bell circuit and prints measurement counts.

---

## Public API

| Symbol | Description |
|---|---|
| `to_braket_circuit(gate_sequence, n_qubits)` | Translate an RQM gate sequence to a Braket `Circuit` |
| `spinor_to_circuit(spinor, qubit)` | Translate a spinor [α, β] into a state-prep circuit |
| `bloch_to_circuit(bloch_vector, qubit)` | Translate a Bloch vector [x, y, z] into a state-prep circuit |
| `quaternion_to_circuit(quaternion, qubit)` | Translate a unit quaternion [w, x, y, z] into a single-qubit circuit |
| `run_local(circuit, shots)` | Execute on the local Braket simulator |
| `run_device(circuit, device_arn, s3_folder, shots)` | Execute on an AWS Braket device |
| `BraketResult` | Friendly wrapper around Braket task results |

---

## Development

Run tests:

```bash
pytest
```

Install development dependencies:

```bash
pip install -r requirements-dev.txt
```

---

## Architectural Rules

This repository follows strict architecture boundaries.

### Canonical math belongs in:

```
rqm-core
```

This includes:

* quaternion algebra
* spinor normalization
* Bloch conversions
* SU(2) matrix generation

---

### `rqm-braket` must NOT implement:

* quaternion math
* spinor math
* Bloch sphere math
* SU(2) algebra

All such functionality must be imported from:

```
rqm_core
```

---

## Project Status

Initial release goal:

* single-qubit translation
* Braket LocalSimulator execution
* minimal device wrapper
* example circuits

Future versions may add:

* multi-qubit translators
* device calibration helpers
* hybrid Braket workflows
* expanded result utilities

---

## License

MIT License

Copyright (c) RQM Technologies
- See `AGENTS.md` for full contribution rules.