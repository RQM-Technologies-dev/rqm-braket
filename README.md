# rqm-braket

[![PyPI version](https://img.shields.io/pypi/v/rqm-braket.svg)](https://pypi.org/project/rqm-braket/)
[![Python versions](https://img.shields.io/pypi/pyversions/rqm-braket.svg)](https://pypi.org/project/rqm-braket/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Documentation](https://img.shields.io/badge/docs-rqmtechnologies.com-blue.svg)](https://docs.rqmtechnologies.com)
[![Website](https://img.shields.io/badge/website-rqmtechnologies.com-informational.svg)](https://rqmtechnologies.com)

Amazon Braket backend for the **Resonant Quantum Mechanics (RQM)** ecosystem.

`rqm-braket` executes **compiled RQM programs** on:

- the **Amazon Braket Local Simulator**
- **AWS Braket quantum devices**

This package is a **backend adapter**, not a compiler and not a math engine.

---

## 🌐 RQM Platform

This repository is part of the RQM Technologies ecosystem.

→ Website: https://rqmtechnologies.com  
→ Documentation: https://docs.rqmtechnologies.com

---

## Installation

```bash
pip install rqm-braket
```

`rqm-braket` depends on `rqm-compiler` for compiled program input and `amazon-braket-sdk` for execution.

Development install:

```bash
pip install -e .
```

---

## Where This Fits

```text
rqm-core → rqm-compiler → rqm-braket
```

This package provides the **Amazon Braket execution backend** for programs compiled through the RQM compiler stack.

| Layer | Responsibility |
|---|---|
| `rqm-core` | Canonical math foundation (quaternion, spinor, Bloch, SU(2)) |
| `rqm-compiler` | Compile RQM objects into backend-agnostic instructions |
| `rqm-braket` | Execute compiled programs on Amazon Braket |

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

## Next Steps

- 📖 Documentation: https://docs.rqmtechnologies.com
- 🌐 Website: https://rqmtechnologies.com
- 🔗 Related package: [`rqm-compiler`](https://github.com/RQM-Technologies-dev/rqm-compiler) — the canonical instruction layer that feeds into this backend

---

## License

MIT License

Copyright (c) RQM Technologies
