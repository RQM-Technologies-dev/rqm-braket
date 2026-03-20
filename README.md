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

### 4. Convenience Bridges (rqm-core delegation)

`rqm-braket` exposes thin bridge functions for users who want to prepare
quantum states without going through the compiler first.

> **These bridges are not the primary API.**  
> For production use, prefer the compiler-first path.
>
> ```
> rqm-compiler → compiled_program → backend.run(...)
> ```
>
> Bridges are intended for students, quick experiments, and direct state
> preparation.  All underlying mathematics is handled by `rqm-core`.

#### `spinor_to_circuit(alpha, beta, target=0)`

Prepares the qubit state `|ψ⟩ = α|0⟩ + β|1⟩` from the given spinor.

Bloch-sphere math is delegated to `rqm_core.state_to_bloch`.

```python
import math
from rqm_braket import spinor_to_circuit

s = 1 / math.sqrt(2)
circuit = spinor_to_circuit(s, s)   # prepares |+⟩
```

#### `bloch_to_circuit(theta, phi, target=0)`

Prepares the qubit state parameterized by Bloch-sphere polar angles.

```python
import math
from rqm_braket import bloch_to_circuit

circuit = bloch_to_circuit(math.pi / 2, 0.0)  # prepares |+⟩
```

#### `Quaternion` (re-exported from rqm-core)

The `Quaternion` class from `rqm-core` is re-exported for user convenience.
All quaternion mathematics lives in `rqm-core`.

```python
from rqm_braket import Quaternion

q = Quaternion.from_axis_angle("z", math.pi / 2)
```

---

## What This Package Does NOT Do

`rqm-braket` does **not implement** canonical quantum mathematics.

It **delegates** all math operations to `rqm-core`:

| Operation | Owner |
|-----------|-------|
| Quaternion algebra | `rqm-core` |
| Spinor normalization | `rqm-core` |
| Bloch sphere conversions | `rqm-core` |
| SU(2) matrix math | `rqm-core` |
| Circuit compilation logic | `rqm-compiler` |
| Backend-agnostic instruction design | `rqm-compiler` |

The rule is: **rqm-braket may call math, but never define it.**

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

## Usage Modes

`rqm-braket` supports two entry points depending on your audience and use case.

### Mode 1 — Compiler-first (recommended for production)

```
rqm-compiler → compiled_program → backend.run(...)
```

```python
from rqm_braket import BraketBackend, RQMGate

backend = BraketBackend()
result = backend.run_local([
    RQMGate("H", target=0),
    RQMGate("CNOT", control=0, target=1),
], shots=500)
print(result.counts)
```

Intended for: researchers, engineers, production workflows.

### Mode 2 — Bridge functions (convenient for exploration)

```
spinor_to_circuit(...)
bloch_to_circuit(...)
```

```python
import math
from rqm_braket import spinor_to_circuit, bloch_to_circuit, run_local

# From a spinor
s = 1 / math.sqrt(2)
circuit = spinor_to_circuit(s, s)
result = run_local(circuit, shots=200)
print(result.counts)

# From Bloch angles
circuit = bloch_to_circuit(math.pi / 2, 0.0)
result = run_local(circuit, shots=200)
print(result.counts)
```

Intended for: students, tutorials, quick experiments.

> All quantum mathematics (Bloch conversion, spinor normalization) is
> delegated to `rqm-core`.  `rqm-braket` only maps the results to gates.

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

### Core backend API

```python
BraketBackend
BraketTranslator
RQMGate
compile_to_braket_circuit
run_local
run_device
BraketResult
```

### Convenience bridges (rqm-core delegation)

```python
spinor_to_circuit   # spinor (α, β) → Braket Circuit
bloch_to_circuit    # Bloch angles (θ, φ) → Braket Circuit
Quaternion          # re-exported from rqm-core
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

### Math Delegation

`rqm-braket` does not implement canonical quantum mathematics.

All physics and math operations are delegated to `rqm-core`:

```
rqm-core     = physics + math
rqm-compiler = structure
rqm-braket   = translation + execution
```

The rule: **rqm-braket may call math, but never define it.**

---

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
