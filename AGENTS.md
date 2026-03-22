# AGENTS.md

Guidelines for AI agents and contributors working in the `rqm-braket` repository.

---

## Repository Purpose

`rqm-braket` is the **Amazon Braket execution bridge** for the RQM ecosystem.

This repository adapts RQM objects and operations into **Amazon Braket circuits and execution workflows**.

It is **not a mathematics library**.

---

## Architecture Discipline

The RQM software stack is layered.

```
rqm-core
↑
math engine

rqm-qiskit / rqm-braket
↑
execution bridges

rqm-notebooks
↑
examples / tutorials
```

---

## Canonical Math Rule

All canonical math belongs in:

```
rqm-core
```

This includes:

- quaternion algebra
- spinor operations
- Bloch sphere math
- SU(2) matrix operations

---

## Strict Prohibitions

AI agents **must not implement or duplicate**:

- quaternion algebra
- spinor normalization
- Bloch conversions
- SU(2) gate math

If functionality is needed:

```
import from rqm_core
```

If functionality does not exist in `rqm-core`:

1. leave a TODO
2. propose adding it to `rqm-core`
3. do not implement it locally

---

## What This Repo SHOULD Contain

Acceptable code includes:

### Translation layer

Converts compiled program objects (from `rqm-compiler`) to Braket circuits.

Primary class: `BraketTranslator`
Convenience function: `compile_to_braket_circuit(compiled_program)`

---

### Result Wrappers

Classes that wrap Braket output objects.

Example:

```
BraketResult
```

---

### Execution Helpers

Utilities that run circuits on:

- LocalSimulator (`run_local`)
- AWS Braket devices — synchronous (`run_device`) and asynchronous (`run_device_async`)
- Task status polling (`get_task_status`, `get_task_result`)
- Device discovery (`list_devices`)
- Descriptor-first execution (`run_descriptors`)

Async task functions must **not embed math logic**.  They only wrap Braket
SDK calls and convert exceptions into `BraketDeviceError`.

---

### Backend Object

Unified entry point: `BraketBackend`

---

## Example Code Policy

Examples should:

- demonstrate usage
- remain small and readable
- avoid reimplementing math

Examples should **import from `rqm-core` when needed**.

---

## Testing Guidelines

Tests must:

- verify imports
- verify translators return valid Braket circuits
- verify result wrappers behave correctly
- test local simulator execution

Tests must **not require AWS credentials**.

---

## Code Style

Follow these guidelines:

- use Python type hints
- keep functions small
- prefer clarity over abstraction
- write docstrings for public APIs

---

## File Responsibilities

| File | Responsibility |
|---|---|
| `translator.py` | `BraketTranslator`, `RQMGate`, `compile_to_braket_circuit` |
| `translators.py` | Backward-compat shim; legacy dict-based `to_braket_circuit` |
| `execution.py` | `run_local`, `run_device`, `run_device_async`, `get_task_status`, `get_task_result`, `list_devices`, `run_descriptors`, `BraketDeviceError` |
| `devices.py` | Backward-compat shim re-exporting from `execution.py` |
| `api.py` | Flask `Blueprint` (`api_blueprint`) exposing `/run`, `/run/async`, `/tasks/<arn>/status`, `/tasks/<arn>/result`, `/devices` endpoints |
| `backend.py` | `BraketBackend` unified backend object |
| `circuits.py` | Lightweight demo circuit builders (Bell, GHZ, etc.) |
| `results.py` | `BraketResult` wrapper around Braket task results |
| `types.py` | `Descriptor` and `DescriptorList` type aliases |
| `__init__.py` | Re-exports the public API only |

---

## Design Philosophy

`rqm-braket` is intentionally thin.

The goal is **backend integration**, not feature expansion.

Shared logic should always migrate downward into:

```
rqm-core
```

never upward into bridge repositories.

---

## Pull Request Checklist

- [ ] No canonical math added (quaternion / spinor / Bloch / SU(2))
- [ ] All new public symbols have type hints and docstrings
- [ ] Tests added for new functionality
- [ ] Tests pass offline (no real AWS credentials)
- [ ] `AGENTS.md` and `README.md` updated if API changed

---

## Contributor Reminder

If you find yourself writing quaternion math here:

**STOP.**

That code belongs in:

```
rqm-core
```
