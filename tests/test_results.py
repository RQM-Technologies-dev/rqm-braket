"""Tests for rqm_braket.results.BraketResult."""

from collections import Counter
from unittest.mock import MagicMock, PropertyMock

import pytest

from rqm_braket.results import BraketResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_raw(
    counts: dict[str, int] | None = None,
    probabilities: dict[str, float] | None = None,
    task_metadata: object = None,
) -> MagicMock:
    """Create a mock ``GateModelQuantumTaskResult``."""
    raw = MagicMock()
    raw.measurement_counts = Counter(counts if counts is not None else {"00": 70, "11": 30})
    raw.measurement_probabilities = probabilities
    raw.task_metadata = task_metadata
    return raw


# ---------------------------------------------------------------------------
# counts
# ---------------------------------------------------------------------------


def test_counts_returns_counter() -> None:
    raw = _make_raw({"00": 60, "11": 40})
    result = BraketResult(raw)
    assert isinstance(result.counts, Counter)
    assert result.counts["00"] == 60
    assert result.counts["11"] == 40


def test_counts_total() -> None:
    raw = _make_raw({"00": 70, "11": 30})
    result = BraketResult(raw)
    assert sum(result.counts.values()) == 100


# ---------------------------------------------------------------------------
# shots
# ---------------------------------------------------------------------------


def test_shots_equals_sum_of_counts() -> None:
    raw = _make_raw({"00": 70, "11": 30})
    result = BraketResult(raw)
    assert result.shots == 100


def test_shots_zero_when_empty() -> None:
    raw = _make_raw({})
    result = BraketResult(raw)
    assert result.shots == 0


# ---------------------------------------------------------------------------
# probabilities — from measurement_probabilities when available
# ---------------------------------------------------------------------------


def test_probabilities_from_raw_when_available() -> None:
    raw = _make_raw(
        counts={"00": 50, "11": 50},
        probabilities={"00": 0.5, "11": 0.5},
    )
    result = BraketResult(raw)
    assert abs(result.probabilities["00"] - 0.5) < 1e-9
    assert abs(result.probabilities["11"] - 0.5) < 1e-9


def test_probabilities_sum_to_one() -> None:
    raw = _make_raw({"00": 70, "11": 30})
    result = BraketResult(raw)
    total = sum(result.probabilities.values())
    assert abs(total - 1.0) < 1e-9


def test_probabilities_values_in_range() -> None:
    raw = _make_raw({"00": 70, "11": 30})
    result = BraketResult(raw)
    for prob in result.probabilities.values():
        assert 0.0 <= prob <= 1.0


def test_probabilities_empty_when_no_shots() -> None:
    raw = _make_raw({})
    result = BraketResult(raw)
    assert result.probabilities == {}


# ---------------------------------------------------------------------------
# metadata
# ---------------------------------------------------------------------------


def test_metadata_returns_dict() -> None:
    meta = MagicMock()
    meta.dict.return_value = {"taskId": "abc123", "shots": 100}
    raw = _make_raw(task_metadata=meta)
    result = BraketResult(raw)
    data = result.metadata
    assert isinstance(data, dict)
    assert data["taskId"] == "abc123"


def test_metadata_returns_empty_dict_on_exception() -> None:
    """If metadata access raises, an empty dict is returned."""
    raw = MagicMock()
    raw.measurement_counts = Counter({"0": 100})
    raw.measurement_probabilities = None
    type(raw).task_metadata = PropertyMock(side_effect=RuntimeError("no meta"))
    result = BraketResult(raw)
    assert result.metadata == {}


# ---------------------------------------------------------------------------
# raw attribute
# ---------------------------------------------------------------------------


def test_raw_attribute_is_preserved() -> None:
    raw = _make_raw()
    result = BraketResult(raw)
    assert result.raw is raw


# ---------------------------------------------------------------------------
# most_likely_bitstring
# ---------------------------------------------------------------------------


def test_most_likely_bitstring_returns_highest_count() -> None:
    raw = _make_raw({"00": 70, "11": 30})
    result = BraketResult(raw)
    assert result.most_likely_bitstring() == "00"


def test_most_likely_bitstring_tie_returns_a_winner() -> None:
    """When counts are equal, one of the tied bitstrings is returned."""
    raw = _make_raw({"00": 50, "11": 50})
    result = BraketResult(raw)
    assert result.most_likely_bitstring() in {"00", "11"}


def test_most_likely_bitstring_single_outcome() -> None:
    raw = _make_raw({"01": 100})
    result = BraketResult(raw)
    assert result.most_likely_bitstring() == "01"


def test_most_likely_bitstring_raises_on_zero_shots() -> None:
    raw = _make_raw({})
    result = BraketResult(raw)
    with pytest.raises(ValueError, match="No measurements"):
        result.most_likely_bitstring()


# ---------------------------------------------------------------------------
# probability_of
# ---------------------------------------------------------------------------


def test_probability_of_known_outcome() -> None:
    raw = _make_raw({"00": 70, "11": 30})
    result = BraketResult(raw)
    assert abs(result.probability_of("00") - 0.7) < 1e-9


def test_probability_of_missing_outcome_returns_zero() -> None:
    raw = _make_raw({"00": 100})
    result = BraketResult(raw)
    assert result.probability_of("11") == 0.0


def test_probability_of_sums_correctly() -> None:
    raw = _make_raw({"00": 60, "11": 40})
    result = BraketResult(raw)
    assert abs(result.probability_of("00") + result.probability_of("11") - 1.0) < 1e-9
