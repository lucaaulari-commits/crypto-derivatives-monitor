"""Tests for src/metrics.py with tiny hand-made data.

Every expected value can be checked with a calculator; the arithmetic is in the comments.
Run from the repository root:  python -m pytest
"""

import math

import pandas as pd
import pytest

from src.metrics import (
    add_metrics,
    annualized_rate,
    cumulative_funding,
    funding_interval_hours,
    moving_average,
)

HOUR_MS = 3_600_000
DAY_MS = 24 * HOUR_MS


def test_interval_constant_8h():
    timestamps = pd.Series([0, 8 * HOUR_MS, 16 * HOUR_MS])
    # 8h - 0h = 8, 16h - 8h = 8; the first row copies the second
    assert list(funding_interval_hours(timestamps)) == [8, 8, 8]


def test_interval_changes_from_8h_to_4h():
    timestamps = pd.Series([0, 8 * HOUR_MS, 12 * HOUR_MS, 16 * HOUR_MS])
    # 8 - 0 = 8, 12 - 8 = 4, 16 - 12 = 4
    assert list(funding_interval_hours(timestamps)) == [8, 8, 4, 4]


def test_annualized_8h():
    # 0.0001 * 8760 / 8 = 0.0001 * 1095 = 0.1095 (10.95% per year)
    assert annualized_rate(0.0001, 8) == pytest.approx(0.1095)


def test_annualized_4h_is_double_8h():
    # same rate paid twice as often: 0.0001 * 8760 / 4 = 0.0001 * 2190 = 0.219
    assert annualized_rate(0.0001, 4) == pytest.approx(0.219)


def test_annualized_negative_rate():
    # -0.0002 * 1095 = -0.219 (shorts pay longs)
    assert annualized_rate(-0.0002, 8) == pytest.approx(-0.219)


def test_cumulative_funding():
    rates = pd.Series([0.0001, 0.0002, -0.0001])
    # 0.0001 | 0.0001 + 0.0002 = 0.0003 | 0.0003 - 0.0001 = 0.0002
    assert list(cumulative_funding(rates)) == pytest.approx([0.0001, 0.0003, 0.0002])


def test_moving_average_regular_data():
    # one value per day: 1, 2, 3, 4, 5 ; window = 2 days, i.e. times in (t - 2d, t]
    df = pd.DataFrame({
        "time": pd.to_datetime([0, 1, 2, 3, 4], unit="D", utc=True),
        "x": [1.0, 2.0, 3.0, 4.0, 5.0],
    })
    result = list(moving_average(df, "x", days=2))
    # day 0 and day 1: less than 2 days of history -> empty (NaN)
    assert math.isnan(result[0])
    assert math.isnan(result[1])
    # day 2: (2 + 3) / 2 = 2.5 ; day 3: (3 + 4) / 2 = 3.5 ; day 4: (4 + 5) / 2 = 4.5
    assert result[2:] == pytest.approx([2.5, 3.5, 4.5])


def test_moving_average_uses_time_not_row_count():
    # irregular spacing: day 0, day 1, day 1.5, day 2 ; window = 1 day
    df = pd.DataFrame({
        "time": pd.to_datetime([0, 24, 36, 48], unit="h", utc=True),
        "x": [2.0, 4.0, 6.0, 8.0],
    })
    result = list(moving_average(df, "x", days=1))
    assert math.isnan(result[0])  # day 0: window not full yet
    # day 1   -> window (day 0, day 1]     = [4]       -> 4
    # day 1.5 -> window (day 0.5, day 1.5] = [4, 6]    -> (4 + 6) / 2 = 5
    # day 2   -> window (day 1, day 2]     = [6, 8]    -> (6 + 8) / 2 = 7
    assert result[1:] == pytest.approx([4.0, 5.0, 7.0])


def test_add_metrics_end_to_end():
    # rows given out of order on purpose: add_metrics must sort them by time
    df = pd.DataFrame({
        "timestamp": [16 * HOUR_MS, 0, 8 * HOUR_MS],
        "funding_rate": [0.0003, 0.0001, 0.0002],
    })
    out = add_metrics(df)

    assert list(out["timestamp"]) == [0, 8 * HOUR_MS, 16 * HOUR_MS]
    assert list(out["interval_hours"]) == [8, 8, 8]
    # 0.0001 * 1095 = 0.1095 ; 0.0002 * 1095 = 0.219 ; 0.0003 * 1095 = 0.3285
    assert list(out["annualized"]) == pytest.approx([0.1095, 0.219, 0.3285])
    # 0.0001 | 0.0001 + 0.0002 = 0.0003 | 0.0003 + 0.0003 = 0.0006
    assert list(out["cumulative"]) == pytest.approx([0.0001, 0.0003, 0.0006])
    # only 16 hours of data: no full 7-day or 30-day window yet
    assert out["annualized_ma_7d"].isna().all()
    assert out["annualized_ma_30d"].isna().all()
