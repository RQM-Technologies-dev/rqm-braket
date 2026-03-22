# rqm-braket

Amazon Braket backend for the **Resonant Quantum Mechanics (RQM)** ecosystem.

`rqm-braket` executes **compiled RQM programs** on:

- the **Amazon Braket Local Simulator**
- **AWS Braket quantum devices**

This package is a **backend adapter**, not a compiler and not a math engine.
It also serves as the **execution engine** for **RQM Studio** (via `rqm-api`),
supporting synchronous and asynchronous job submission, device discovery, and
descriptor-first workflows.

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
                              |
                          rqm-api
                              |
                         RQM Studio
```

### Layer responsibilities

| Layer            | Responsibility |
|------------------|----------------|
| `rqm-core`       | Canonical math (quaternion, spinor, Bloch, SU(2)) |
| `rqm-compiler`   | Compile RQM objects into backend-agnostic instructions |
| `rqm-braket`     | Execute compiled programs on Amazon Braket |
| `rqm-qiskit`     | Execute compiled programs on Qiskit |
| `rqm-api`        | REST API layer exposing backends to RQM Studio |
| `rqm-notebooks`  | Examples, demos, tutorials |

---

## What This Package Does

`rqm-braket` provides five core capabilities:

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

### 2. Synchronous Execution

Run circuits on:

- Local simulator (offline-safe)
- AWS Braket devices (synchronous — blocks until complete)

```
Circuit → execution → BraketResult
```

Handled by:

```
run_local(...)
run_device(...)
BraketBackend
```

---

### 3. Asynchronous Execution

Submit jobs without blocking and poll for results later:

```
Circuit → submit → task_arn → poll status → retrieve result
```

Handled by:

```
run_device_async(...)   → task ARN
get_task_status(arn)    → "QUEUED" / "RUNNING" / "COMPLETED" / ...
get_task_result(arn)    → BraketResult
```

---

### 4. Device Discovery

List available AWS Braket devices:

```python
from rqm_braket import list_devices

simulators = list_devices(device_types=["SIMULATOR"])
qpu_devices = list_devices(device_types=["QPU"])
all_devices = list_devices()
```

Returns JSON-serializable dicts with `deviceArn`, `deviceName`,
`deviceType`, `status`, and `providerName`.

---

### 5. Descriptor-first Execution

Execute directly from canonical descriptors (JSON output of
`rqm_compiler.Circuit.to_descriptors()`):

```python
from rqm_braket import run_descriptors

descriptors = [
    {"gate": "h", "targets": [0], "controls": [], "params": {}},
    {"gate": "cx", "targets": [1], "controls": [0], "params": {}},
]
result = run_descriptors(descriptors, shots=200)
print(result.counts)
```

This is the primary API entry point for `rqm-api` / RQM Studio.

---

### 6. Result Wrapping

Normalize Braket outputs into a simple interface:

```python
result.counts
result.probabilities
result.shots
result.most_likely_bitstring()
result.to_dict()                                    # base fields
result.to_dict(include_probabilities=True)          # + probabilities
result.to_dict(include_task_id=True)                # + task ARN
result.to_dict(include_status=True)                 # + task status
```

---

### 7. Convenience Bridges (rqm-core delegation)

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

`rqm-braket` supports multiple entry points depending on your audience and use case.

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

### Mode 2 — Descriptor-first (recommended for API layer)

```
rqm-api → descriptors (JSON) → run_descriptors(...)
```

```python
from rqm_braket import run_descriptors

descriptors = [
    {"gate": "h", "targets": [0], "controls": [], "params": {}},
    {"gate": "cx", "targets": [1], "controls": [0], "params": {}},
]
result = run_descriptors(descriptors, shots=200)
print(result.to_dict(include_probabilities=True))
```

Intended for: the `rqm-api` layer and RQM Studio integration.

### Mode 3 — Asynchronous device execution

```
run_device_async(...) → task_arn → get_task_status(arn) → get_task_result(arn)
```

```python
from rqm_braket import run_device_async, get_task_status, get_task_result

task_arn = run_device_async(
    program,
    device_arn="arn:aws:braket:::device/quantum-simulator/amazon/sv1",
    s3_folder=("my-bucket", "results"),
    shots=100,
)

status = get_task_status(task_arn)
print(status)  # "QUEUED", "RUNNING", "COMPLETED", ...

if status == "COMPLETED":
    result = get_task_result(task_arn)
    print(result.counts)
```

Intended for: long-running QPU jobs where blocking is undesirable.

### Mode 4 — Bridge functions (convenient for exploration)

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

## Running from RQM Studio

RQM Studio communicates with `rqm-api`, which calls into `rqm-braket`.
The recommended call pattern is:

1. **Design circuit** in RQM Studio UI → `rqm-compiler` compiles to descriptors.
2. **Submit job** via `rqm-api` → calls `run_descriptors(descriptors, backend="device", ...)`.
3. **Poll status** via `rqm-api` → calls `get_task_status(task_arn)`.
4. **Retrieve result** via `rqm-api` → calls `get_task_result(task_arn)`.
5. **Visualize** result in RQM Studio → use `result.to_dict(include_probabilities=True)`.

### Device selection

```python
from rqm_braket import list_devices

# List all simulators
simulators = list_devices(device_types=["SIMULATOR"])

# List all QPUs
qpus = list_devices(device_types=["QPU"])

# RQM Studio can display these to the user for device selection
```

### AWS credentials

`rqm-braket` uses the standard AWS credential chain.  Configure via:

- `aws configure` (CLI)
- Environment variables (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_DEFAULT_REGION`)
- IAM roles (recommended for production)

**Never store AWS credentials in code.**

### S3 result storage

Device execution requires an S3 bucket for Braket to store task results.
For large circuits or production deployments, use a dedicated S3 bucket and
prefix managed by `rqm-api` to consolidate result storage across jobs.

```python
result = run_descriptors(
    descriptors,
    backend="device",
    device_arn="arn:aws:braket:us-east-1::device/qpu/ionq/Harmony",
    s3_folder=("your-braket-bucket", "rqm-results"),
    shots=1000,
)
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

### Core backend API

```python
BraketBackend           # unified backend object
BraketTranslator        # compile programs → Braket Circuit
RQMGate                 # typed gate descriptor
compile_to_braket_circuit  # convenience translation
run_local               # execute on local simulator (offline-safe)
run_device              # execute on AWS Braket device (synchronous)
BraketResult            # result wrapper
```

### Async & task management

```python
run_device_async        # submit job → task ARN (non-blocking)
get_task_status         # query task state ("QUEUED" / "RUNNING" / ...)
get_task_result         # retrieve BraketResult for completed task
```

### Device discovery

```python
list_devices            # list available AWS Braket devices
```

### Descriptor-first execution

```python
run_descriptors         # translate descriptors + execute (API-ready)
```

### Error handling

```python
BraketDeviceError       # raised for device/task failures (RuntimeError subclass)
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

### AWS Device (synchronous)

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

### AWS Device (asynchronous)

```python
task_arn = run_device_async(
    program,
    device_arn="arn:aws:braket:...",
    s3_folder=("bucket", "prefix"),
    shots=100,
)
status = get_task_status(task_arn)     # "QUEUED", "RUNNING", "COMPLETED", ...
result = get_task_result(task_arn)     # BraketResult (blocks until done)
```

---

### Descriptor-first (API layer)

```python
result = run_descriptors(
    descriptors,
    shots=100,
    backend="local",   # or "device"
)
```

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
* async execution (`run_device_async`, `get_task_status`, `get_task_result`)
* device discovery (`list_devices`)
* descriptor-first execution (`run_descriptors`)
* extended result serialization (`BraketResult.to_dict` optional extras)
* `BraketDeviceError` for friendly error handling
* backward-compatibility shims (deprecated)

---

## Roadmap

Future improvements may include:

* parameter binding support via Braket `FreeParameter`
  (TODO: propose adding parametric circuit support to `rqm-core` or `rqm-compiler`)
* batched execution
* hybrid Braket workflows
* richer result analysis
* multi-qubit optimization paths
* S3 result storage managed by `rqm-api`

---

## License

MIT License

Copyright (c) RQM Technologies
