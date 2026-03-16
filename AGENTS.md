# AGENTS.md — rqm-braket Contribution Rules

This file defines strict rules for all contributors and AI agents working in this repository.

---

## Core Principle

`rqm-braket` is a **thin adapter layer** between `rqm-core` and Amazon Braket.
It does **not** own any canonical quantum math.

---

## What belongs here

- Translation of RQM objects (gates, circuits, states) into Braket SDK objects.
- Execution helpers for local simulator and AWS Braket devices.
- Result normalization wrappers that convert Braket outputs to RQM-friendly objects.
- Tests and examples proving end-to-end usage.

## What does NOT belong here

- Quaternion math or arithmetic.
- Spinor representations or operations.
- Bloch sphere math.
- SU(2) matrix construction.
- Any canonical RQM algorithm implementation.

All of the above live exclusively in [`rqm-core`](https://github.com/RQM-Technologies-dev/rqm-core).
**Import from `rqm-core`. Do not reimplement.**

---

## Design Rules

1. **Thin wrappers over abstraction-heavy design.**
   Keep classes and functions small and focused.

2. **Import, don't reimplement.**
   If you need quaternion math, spinor math, or SU(2) operations, import them from `rqm-core`.

3. **Stable public API.**
   The public symbols in `rqm_braket/__init__.py` form the public contract.
   Do not remove or rename them without a deprecation notice.

4. **Offline-safe tests.**
   All tests must pass without AWS credentials.
   Mock cloud execution paths; use the local Braket simulator for circuit tests.

5. **No dead code.**
   Do not add speculative features. Keep the codebase narrow and working.

6. **Type hints and docstrings on all public symbols.**

---

## File Responsibilities

| File | Responsibility |
|---|---|
| `translators.py` | RQM gate/state → Braket `Circuit` translation |
| `circuits.py` | Lightweight demo circuit builders (Bell, GHZ, etc.) |
| `results.py` | `BraketResult` wrapper around Braket task results |
| `devices.py` | `run_local` and `run_device` execution helpers |
| `__init__.py` | Re-exports the public API only |

---

## Pull Request Checklist

- [ ] No canonical math added (quaternion / spinor / Bloch / SU(2))
- [ ] All new public symbols have type hints and docstrings
- [ ] Tests added for new functionality
- [ ] Tests pass offline (no real AWS credentials)
- [ ] `AGENTS.md` and `README.md` updated if API changed
