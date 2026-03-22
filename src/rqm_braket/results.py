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

    def most_likely_bitstring(self) -> str:
        """Return the bitstring with the highest measurement count.

        Returns
        -------
        str
            The most frequently observed outcome bitstring, e.g. ``"00"``.

        Raises
        ------
        ValueError
            If no measurements were recorded (zero shots).

        Examples
        --------
        >>> result.most_likely_bitstring()
        '00'
        """
        counts = self.counts
        if not counts:
            raise ValueError("No measurements recorded (zero shots).")
        return max(counts, key=counts.__getitem__)

    def probability_of(self, bitstring: str) -> float:
        """Return the empirical probability of a specific outcome bitstring.

        Parameters
        ----------
        bitstring:
            The outcome bitstring to look up, e.g. ``"00"`` or ``"11"``.

        Returns
        -------
        float
            Probability in [0, 1].  Returns ``0.0`` if the bitstring was
            never observed.

        Examples
        --------
        >>> result.probability_of("00")
        0.48
        """
        return self.probabilities.get(bitstring, 0.0)

    def to_dict(
        self,
        *,
        include_probabilities: bool = False,
        include_task_id: bool = False,
        include_status: bool = False,
    ) -> dict[str, Any]:
        """Return a JSON-serializable dict representation of this result.

        The returned format is designed for API compatibility, suitable for
        returning from HTTP endpoints such as ``POST /run``.

        Parameters
        ----------
        include_probabilities:
            When ``True``, include a ``"probabilities"`` key with the
            empirical outcome probabilities.
        include_task_id:
            When ``True``, include a ``"task_id"`` key with the task ARN
            extracted from the task metadata (``None`` if unavailable).
        include_status:
            When ``True``, include a ``"status"`` key with the task status
            string from metadata (``None`` if unavailable).

        Returns
        -------
        dict
            A dict with the following keys (always present):

            * ``"counts"`` — measurement outcome counts as a plain ``dict``
              mapping bitstring to integer count.
            * ``"shots"`` — total number of shots as an integer.
            * ``"backend"`` — the backend name (always ``"braket"``).
            * ``"metadata"`` — task metadata as a plain dict (may be empty).

            Optional keys (present only when the corresponding flag is
            ``True``):

            * ``"probabilities"`` — empirical probabilities as a ``dict``
              mapping bitstring to ``float`` in [0, 1].
            * ``"task_id"`` — task ARN string or ``None``.
            * ``"status"`` — task status string or ``None``.

        Examples
        --------
        >>> result.to_dict()
        {'counts': {'00': 52, '11': 48}, 'shots': 100, 'backend': 'braket', 'metadata': {}}
        >>> result.to_dict(include_probabilities=True, include_task_id=True)
        {'counts': {...}, 'shots': 100, 'backend': 'braket', 'metadata': {},
         'probabilities': {'00': 0.52, '11': 0.48}, 'task_id': None}
        """
        result: dict[str, Any] = {
            "counts": dict(self.counts),
            "shots": self.shots,
            "backend": "braket",
            "metadata": self.metadata,
        }
        if include_probabilities:
            result["probabilities"] = self.probabilities
        if include_task_id:
            result["task_id"] = self.metadata.get("id") or self.metadata.get("taskId")
        if include_status:
            result["status"] = self.metadata.get("status")
        return result

    # ------------------------------------------------------------------
    # Dunder helpers
    # ------------------------------------------------------------------

    def __repr__(self) -> str:  # pragma: no cover
        top = sorted(self.counts.items(), key=lambda x: -x[1])[:4]
        top_str = ", ".join(f"{k!r}: {v}" for k, v in top)
        return f"BraketResult(shots={self.shots}, counts={{{top_str}}})"
