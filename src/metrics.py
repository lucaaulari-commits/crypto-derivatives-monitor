"""Funding rate metrics.

Input: a DataFrame with one row per funding settlement and the columns
    timestamp     settlement time in milliseconds since 1970-01-01 UTC
    funding_rate  rate of that settlement as a decimal (0.0001 = 0.01%)

Every output rate is also a decimal: multiply by 100 to show it as a percentage.
A positive funding rate means longs pay shorts; negative means shorts pay longs.
"""

import pandas as pd

HOURS_PER_YEAR = 365 * 24   # 8760: crypto perpetuals trade every day of the year
MS_PER_HOUR = 60 * 60 * 1000


def funding_interval_hours(timestamps_ms):
    """Hours between each settlement and the previous one.

    Formula:  interval_i = (timestamp_i - timestamp_(i-1)) / 3,600,000

    The interval is read from the data instead of assumed, because Bybit uses
    different intervals for different symbols (e.g. 4h or 8h) and can change it.
    The first row has no previous settlement, so it takes the interval of the second row.
    """
    intervals = timestamps_ms.diff() / MS_PER_HOUR
    return intervals.bfill()


def annualized_rate(funding_rate, interval_hours):
    """Simple (non-compounded) annualized funding rate.

    Formula:  annualized = funding_rate * (8760 / interval_hours)

    8760 / interval_hours is the number of settlements in one year.
    Example: 0.01% every 8h -> 0.0001 * (8760 / 8) = 0.0001 * 1095 = 10.95% per year.
    """
    return funding_rate * (HOURS_PER_YEAR / interval_hours)


def moving_average(df, column, days):
    """Average of `column` over the last `days` days, using a time-based window.

    Formula:  MA_t = mean of all values whose time is in (t - days, t]

    A time window (not "the last N rows") stays correct if the funding interval changes.
    The first `days` days of history are left empty (NaN) because the window
    does not yet contain a full `days` days of data.
    """
    rolling_mean = df.rolling(f"{days}D", on="time")[column].mean()
    window_not_full = df["time"] < df["time"].iloc[0] + pd.Timedelta(days=days)
    return rolling_mean.mask(window_not_full)


def cumulative_funding(funding_rate):
    """Running total of the funding rate since the first record.

    Formula:  cumulative_t = funding_rate_1 + funding_rate_2 + ... + funding_rate_t

    Meaning: the fraction of position notional a long would have paid
    (a short would have received) holding a constant notional, without compounding.
    Example: 0.0001 + 0.0002 - 0.0001 = 0.0002 = 0.02% of notional.
    """
    return funding_rate.cumsum()


def add_metrics(df):
    """Return a copy of df sorted by time, with all the metric columns added."""
    out = df.sort_values("timestamp").reset_index(drop=True).copy()
    out["time"] = pd.to_datetime(out["timestamp"], unit="ms", utc=True)
    out["interval_hours"] = funding_interval_hours(out["timestamp"])
    out["annualized"] = annualized_rate(out["funding_rate"], out["interval_hours"])
    out["annualized_ma_7d"] = moving_average(out, "annualized", days=7)
    out["annualized_ma_30d"] = moving_average(out, "annualized", days=30)
    out["cumulative"] = cumulative_funding(out["funding_rate"])
    return out
