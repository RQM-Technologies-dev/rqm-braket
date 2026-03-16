"""
rqm_braket.results
==================

Friendly wrapper around Amazon Braket task results.

``BraketResult`` normalises the useful outputs of a Braket
``GateModelQuantumTaskResult`` — counts, probabilities, and task metadata —
without replacing the underlying object.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from braket.tasks import GateModelQuantumTaskResult


class BraketResult:
    """Friendly wrapper around a Braket ``GateModelQuantumTaskResult``.

    Parameters
    ----------
    raw:
        The raw ``GateModelQuantumTaskResult`` returned by a Braket task.

    Attributes
    ----------
    raw:
        The original unwrapped result object.

    Examples
    --------
    >>> from rqm_braket.results import BraketResult
    >>> from rqm_braket.circuits import bell_circuit
    >>> from rqm_braket.devices import run_local
    >>> result = run_local(bell_circuit(), shots=100)
    >>> print(result.counts)
    >>> print(result.probabilities)
    """

    def __init__(self, raw: GateModelQuantumTaskResult) -> None:
        self.raw: GateModelQuantumTaskResult = raw

    # ------------------------------------------------------------------
    # Primary accessors
    # ------------------------------------------------------------------

    @property
    def counts(self) -> Counter[str]:
        """Measurement outcome counts keyed by bitstring.

        Returns
        -------
        collections.Counter[str]
            Maps outcome bitstring (e.g. ``"00"``) to observed count.
        """
        return Counter(self.raw.measurement_counts)

    @property
    def probabilities(self) -> dict[str, float]:
        """Empirical outcome probabilities keyed by bitstring.

        Computed from measurement counts when Braket does not return
        exact probabilities directly.

        Returns
        -------
        dict[str, float]
            Maps outcome bitstring to probability in [0, 1].
        """
        if self.raw.measurement_probabilities is not None:
            return dict(self.raw.measurement_probabilities)
        total = sum(self.counts.values())
        if total == 0:
            return {}
        return {outcome: count / total for outcome, count in self.counts.items()}

    @property
    def shots(self) -> int:
        """Total number of shots (measurements) taken."""
        return int(sum(self.counts.values()))

    @property
    def metadata(self) -> dict[str, Any]:
        """Task metadata as a plain dict.

        Returns an empty dict if metadata is unavailable.
        """
        try:
            meta = self.raw.task_metadata
            return meta.dict() if hasattr(meta, "dict") else {}
        except Exception:  # noqa: BLE001
            return {}

    # ------------------------------------------------------------------
    # Dunder helpers
    # ------------------------------------------------------------------

    def __repr__(self) -> str:  # pragma: no cover
        top = sorted(self.counts.items(), key=lambda x: -x[1])[:4]
        top_str = ", ".join(f"{k!r}: {v}" for k, v in top)
        return f"BraketResult(shots={self.shots}, counts={{{top_str}}})"
