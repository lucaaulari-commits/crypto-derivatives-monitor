"""Download new funding records from Bybit and save them to data/funding_<SYMBOL>.csv.

First run: downloads the full history.
Later runs: downloads only records newer than the last one already saved.

Run from the repository root:  python -m scripts.update
"""

from pathlib import Path

import pandas as pd

from src.bybit_client import fetch_funding_history

SYMBOLS = ["BTCUSDT", "ETHUSDT"]
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
COLUMNS = ["timestamp", "time_utc", "funding_rate"]


def csv_path(symbol):
    return DATA_DIR / f"funding_{symbol}.csv"


def records_to_dataframe(records):
    """Turn the client's list of dicts into a table with a readable UTC time column."""
    df = pd.DataFrame(records, columns=["timestamp", "funding_rate"])
    df["time_utc"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True).dt.strftime("%Y-%m-%d %H:%M")
    return df[COLUMNS]


def update_symbol(symbol):
    """Update the CSV of one symbol and return how many new records were added."""
    path = csv_path(symbol)

    if path.exists():
        existing = pd.read_csv(path)
        last_timestamp = int(existing["timestamp"].max())
        new_records = fetch_funding_history(symbol, stop_at_ms=last_timestamp)
    else:
        existing = pd.DataFrame(columns=COLUMNS)
        new_records = fetch_funding_history(symbol)

    if not new_records:
        return 0

    new = records_to_dataframe(new_records)

    # Combine old and new rows; if a timestamp appears twice keep one copy only.
    if existing.empty:
        combined = new
    else:
        combined = pd.concat([existing, new], ignore_index=True)
    combined = combined.drop_duplicates(subset="timestamp", keep="last")
    combined = combined.sort_values("timestamp")

    DATA_DIR.mkdir(exist_ok=True)
    combined.to_csv(path, index=False)
    return len(combined) - len(existing)


def main():
    for symbol in SYMBOLS:
        added = update_symbol(symbol)
        print(f"{symbol}: {added} new records -> {csv_path(symbol).name}")


if __name__ == "__main__":
    main()
