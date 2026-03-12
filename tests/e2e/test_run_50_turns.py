# tests/e2e/test_run_50_turns.py
from tests.e2e.run_50_turns import _percentile


def test_percentile_p50_midpoint():
    values = [10.0, 20.0, 30.0, 40.0, 50.0]
    assert _percentile(values, 50) == 30.0


def test_percentile_p95_near_end():
    # _percentile uses idx = int(len * p / 100), so for 100 values at p95:
    # idx = int(100 * 95 / 100) = 95 → values[95] = 96.0 (0-indexed, values are 1..100)
    values = list(range(1, 101))  # 1..100
    result = _percentile([float(v) for v in values], 95)
    assert result == 96.0


def test_percentile_empty_returns_none():
    assert _percentile([], 50) is None


def test_percentile_single_value():
    assert _percentile([42.0], 50) == 42.0
