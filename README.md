# rqm-braket

Amazon Braket **lowering and execution bridge** for the **Resonant Quantum
Mechanics (RQM)** ecosystem.

`rqm-braket` receives **compiler-optimized circuit representations** from
`rqm-compiler` and translates them into Amazon Braket circuit and task objects,
then executes them on:

- the **Amazon Braket Local Simulator**
- **AWS Braket quantum devices**

This package is a **backend adapter / execution bridge**, not a compiler, not a
math engine, and not the owner of the public circuit schema.  The canonical
external circuit IR lives in `rqm-circuits`; optimization logic lives in
`rqm-compiler`.  `rqm-braket` is the final, AWS-facing step in that pipeline.

---

## Architecture Overview

The RQM software stack is intentionally layered:

```
              rqm-docs
                  |
  -------------------------------------------
  |               |                         |
rqm-core      rqm-circuits             rqm-notebooks
                  |
            rqm-compiler
                  |
        ----------------------
        |                    |
    rqm-qiskit          rqm-braket
        |                    |
        └────────────────────┘
                  |
            rqm-optimize  (optional)
                  |
              rqm-api
                  |
             RQM Studio
```

### Layer responsibilities

| Layer            | Responsibility |
|------------------|----------------|
| `rqm-core`       | Canonical math (quaternion, spinor, Bloch, SU(2)) |
| `rqm-circuits`   | Canonical **external / public** circuit IR — the shared schema for Studio, API, and inter-service communication |
| `rqm-compiler`   | Parse, optimize, and rewrite circuits in an internal model; produce backend-ready instruction sequences |
| `rqm-braket`     | **Lower** compiler output into Amazon Braket objects; **execute** on local simulator or AWS devices |
| `rqm-qiskit`     | Lower compiler output into Qiskit objects; execute on IBM / Qiskit devices |
| `rqm-optimize`   | Optional backend-adjacent optimization / compression (post-compiler, pre-execution) |
| `rqm-api`        | REST API layer exposing backends to RQM Studio |
| `rqm-notebooks`  | Examples, demos, tutorials |

### Input boundary

The typical data flow from an external caller through to execution is:

```
RQM Studio / API caller
        │ (rqm-circuits payload)
        ▼
   rqm-circuits  ←  public/external circuit schema lives here
        │ (parsed & validated)
        ▼
   rqm-compiler  ←  optimization, rewriting, instruction lowering
        │ (compiler-internal circuit or descriptor list)
        ▼
   rqm-braket    ←  Braket lowering & execution (this package)
        │ (Braket Circuit + task)
        ▼
  Amazon Braket / AWS
```

External callers (RQM Studio, `rqm-api`) originate from **`rqm-circuits`**
payloads.  `rqm-compiler` validates and optimizes those payloads.
`rqm-braket` only sees the compiler-produced output — it does **not** parse
or own the public wire format.

If `rqm-braket` exposes helper functions that accept compiler `Circuit`
objects or descriptor lists directly (e.g. `run_descriptors`, `to_backend_circuit`),
those helpers assume upstream parsing and validation have already happened.

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

> **Note:** In production, descriptor lists originate from `rqm-circuits`
> payloads that have been parsed and optimized by `rqm-compiler` upstream.
> `rqm-braket` receives the compiler-produced output and does not validate
> the public wire format itself.

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

## What This Package Owns and Does NOT Own

### rqm-braket owns

| Capability | Description |
|-----------|-------------|
| Braket lowering | Translation of compiler output into Amazon Braket `Circuit` / task objects |
| Backend execution helpers | `run_local`, `run_device`, `run_device_async` |
| AWS / Braket device integration | Device discovery, task submission, status polling |
| Result normalization | `BraketResult` wrapper around Braket task outputs |

### rqm-braket does NOT own

| Concern | Owner |
|---------|-------|
| Quaternion / SU(2) math | `rqm-core` |
| Spinor normalization | `rqm-core` |
| Bloch sphere conversions | `rqm-core` |
| **Canonical external circuit schema** | **`rqm-circuits`** |
| Optimization pass design | `rqm-compiler` |
| Internal circuit compilation logic | `rqm-compiler` |
| API wire format | `rqm-circuits` / `rqm-api` |
| Studio payload format | `rqm-circuits` / `rqm-api` |

The rule: **rqm-braket may call math and compiler APIs, but never define them.**

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
rqm-circuits → rqm-compiler → compiled_program → backend.run(...)
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

> **Note:** In a full stack flow, the gate sequence originates as an
> `rqm-circuits` payload, is parsed and optimized by `rqm-compiler`, and
> the compiler's output is then passed into `rqm-braket`.  Using `RQMGate`
> directly (as above) is fine for direct scripting and experiments.

### Mode 2 — Descriptor-first (recommended for API layer)

```
rqm-circuits → rqm-compiler → descriptors (JSON) → run_descriptors(...)
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

> **Note:** Descriptor lists are the compiler-internal format produced by
> `rqm_compiler.Circuit.to_descriptors()`.  In Studio / API workflows the
> original circuit is expressed in `rqm-circuits` format and is parsed and
> optimized by `rqm-compiler` before descriptors reach `rqm-braket`.

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

1. **Design circuit** in RQM Studio UI → expressed as an `rqm-circuits` payload.
2. **Compile** via `rqm-compiler` → validates, optimizes, and produces descriptors.
3. **Choose device** via `GET /v1/devices` → calls `list_devices()`.
4. **Submit job** via `POST /v1/run/async` → calls `run_device_async(...)`, returns `task_arn`.
5. **Poll status** via `GET /v1/tasks/<task_arn>/status` → calls `get_task_status(task_arn)`.
6. **Retrieve result** via `GET /v1/tasks/<task_arn>/result` → calls `get_task_result(task_arn)`.
7. **Visualize** result in RQM Studio UI.

For synchronous (blocking) local or device runs use `POST /v1/run`.

`rqm-braket` only participates from step 4 onward.  The public circuit schema
and wire format belong to `rqm-circuits`; `rqm-braket` receives already-
compiled / already-validated data.

### Integrating the Blueprint

```python
from flask import Flask
from rqm_braket.api import api_blueprint

app = Flask(__name__)
app.register_blueprint(api_blueprint, url_prefix="/v1")
```

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

### REST API Blueprint (rqm-api integration)

```python
api_blueprint           # Flask Blueprint — mount in rqm-api Flask application
```

Mount in your `rqm-api` application:

```python
from flask import Flask
from rqm_braket.api import api_blueprint

app = Flask(__name__)
app.register_blueprint(api_blueprint, url_prefix="/v1")
```

Endpoints exposed:

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/v1/run` | Execute circuit synchronously (`local` or `device` backend) |
| `POST` | `/v1/run/async` | Submit circuit to AWS Braket device; returns `task_arn` |
| `GET`  | `/v1/tasks/<task_arn>/status` | Poll task state (`QUEUED`, `RUNNING`, `COMPLETED`, …) |
| `GET`  | `/v1/tasks/<task_arn>/result` | Retrieve result of completed task |
| `GET`  | `/v1/devices` | List available AWS Braket devices |

Install the optional `[api]` extra to pull in Flask:

```bash
pip install rqm-braket[api]
```

---

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
rqm-core      = physics + math
rqm-circuits  = public/external circuit schema
rqm-compiler  = optimization + internal instruction model
rqm-braket    = Braket lowering + execution
```

The rule: **rqm-braket may call math and compiler APIs, but never define them.**

---

### Thin Adapter Layer

`rqm-braket` is intentionally minimal:

* no duplicated logic
* no second IR
* no math reimplementation
* no redefinition of the public circuit schema

---

### Compiler Boundary

Direct inputs to `rqm-braket` come from:

```
rqm-compiler
```

The full upstream path is:

```
rqm-circuits  (public schema)
      ↓
rqm-compiler  (optimization / internal IR)
      ↓
rqm-braket    (Braket lowering + execution)
```

This ensures:

* backend independence
* clean separation of concerns
* extensibility to new platforms
* `rqm-braket` never owns or parses the public wire format

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
