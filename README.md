# rqm-braket

Amazon Braket backend for the **Resonant Quantum Mechanics (RQM)** ecosystem.

`rqm-braket` executes **compiled RQM programs** on:

- the **Amazon Braket Local Simulator**
- **AWS Braket quantum devices**

This package is a **backend adapter**, not a compiler and not a math engine.

---

## Architecture Overview

The RQM software stack is intentionally layered:

```
              rqm-docs
                  |
  -----------------------------------
  |               |                |
rqm-core      rqm-compiler     rqm-notebooks
                  |
        ----------------------
        |                    |
    rqm-qiskit          rqm-braket
```

### Layer responsibilities

| Layer            | Responsibility |
|------------------|----------------|
| `rqm-core`       | Canonical math (quaternion, spinor, Bloch, SU(2)) |
| `rqm-compiler`   | Compile RQM objects into backend-agnostic instructions |
| `rqm-braket`     | Execute compiled programs on Amazon Braket |
| `rqm-qiskit`     | Execute compiled programs on Qiskit |
| `rqm-notebooks`  | Examples, demos, tutorials |

---

## What This Package Does

`rqm-braket` provides three core capabilities:

---

### 1. Translation

Convert **compiled programs** into Braket `Circuit` objects.

```
compiled_program → Braket Circuit
```

Handled by:

```
BraketTranslator
compile_to_braket_circuit(...)
```

---

### 2. Execution

Run circuits on:

- Local simulator (offline-safe)
- AWS Braket devices

```
Circuit → execution → result
```

Handled by:

```
run_local(...)
run_device(...)
BraketBackend
```

---

### 3. Result Wrapping

Normalize Braket outputs into a simple interface:

```python
result.counts
result.probabilities
result.shots
result.most_likely_bitstring()
```

---

## What This Package Does NOT Do

`rqm-braket` deliberately does **not** include:

* quaternion math
* spinor math
* Bloch sphere logic
* SU(2) algebra
* circuit compilation logic
* backend-agnostic instruction design

These belong to:

```
rqm-core
rqm-compiler
```

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

## Quick Start (Compiled Program)

```python
from rqm_braket import BraketBackend, RQMGate

program = [
    RQMGate("H", target=0),
    RQMGate("CNOT", control=0, target=1),
]

backend = BraketBackend()

result = backend.run_local(program, shots=1000)

print(result.counts)
```

---

## Direct Translation Example

```python
from rqm_braket import compile_to_braket_circuit, RQMGate

program = [
    RQMGate("RX", target=0, angle=1.57),
]

circuit = compile_to_braket_circuit(program)

print(circuit)
```

---

## Examples

### Local simulator

```
examples/basic_local_simulator.py
```

### Bell state

```
examples/bell_state_demo.py
```

### Compiled program demo

```
examples/compiled_program_demo.py
```

---

## Public API

```python
BraketBackend
BraketTranslator
RQMGate
compile_to_braket_circuit
run_local
run_device
BraketResult
```

---

## Execution Modes

### Local (offline-safe)

```python
result = run_local(program, shots=100)
```

No AWS credentials required.

---

### AWS Device

```python
result = run_device(
    program,
    device_arn="arn:aws:braket:...",
    s3_folder=("bucket", "prefix"),
    shots=100
)
```

Requires standard AWS + Braket configuration.

---

## Development

Run tests:

```bash
pytest
```

All tests are:

* offline-safe
* no AWS credentials required
* include mocked cloud execution

---

## Design Principles

### Thin Adapter Layer

`rqm-braket` is intentionally minimal:

* no duplicated logic
* no second IR
* no math reimplementation

---

### Compiler Boundary

All inputs come from:

```
rqm-compiler
```

This ensures:

* backend independence
* clean separation of concerns
* extensibility to new platforms

---

### Backend Agnostic Design

Because the compiler produces a canonical instruction format:

```
rqm-compiler → rqm-qiskit
rqm-compiler → rqm-braket
rqm-compiler → future backends
```

---

## Versioning

Current version: `0.2.0`

This release introduces:

* compiler-based architecture
* `BraketBackend` abstraction
* clean translation/execution separation
* backward-compatibility shims (deprecated)

---

## Roadmap

Future improvements may include:

* parameter binding support
* batched execution
* hybrid Braket workflows
* richer result analysis
* multi-qubit optimization paths

---

## License

MIT License

Copyright (c) RQM Technologies
