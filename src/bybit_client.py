"""Minimal client for Bybit's public funding rate history (API v5, no key needed).

Docs: https://bybit-exchange.github.io/docs/v5/market/history-fund-rate
"""

import time

import requests

URL = "https://api.bybit.com/v5/market/funding/history"
PAGE_LIMIT = 200          # maximum records the API returns per call
PAUSE_SECONDS = 0.5       # pause between calls, to be polite with the API
TIMEOUT_SECONDS = 10      # give up on a single HTTP request after this long
MAX_ATTEMPTS = 3          # attempts per page before giving up


class BybitAPIError(Exception):
    """Raised when Bybit answers but reports an error (retCode != 0)."""


def fetch_funding_page(symbol, end_time_ms=None, category="linear"):
    """Download one page (up to 200 records) ending at end_time_ms.

    Without end_time_ms the API returns the most recent records.
    Returns a list of dicts: {"timestamp": int ms, "funding_rate": float}.
    """
    params = {"category": category, "symbol": symbol, "limit": PAGE_LIMIT}
    if end_time_ms is not None:
        params["endTime"] = end_time_ms

    # Network problems (timeouts, 5xx, 403...) are retried a few times,
    # waiting a bit longer after each failure.
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            response = requests.get(URL, params=params, timeout=TIMEOUT_SECONDS)
            response.raise_for_status()  # raises on HTTP 4xx / 5xx
            break
        except requests.RequestException:
            if attempt == MAX_ATTEMPTS:
                raise
            time.sleep(2 * attempt)

    # Bybit can answer HTTP 200 but still report an error inside the JSON.
    payload = response.json()
    if payload["retCode"] != 0:
        raise BybitAPIError(f"retCode={payload['retCode']} retMsg={payload['retMsg']}")

    # The API sends numbers as strings: convert them here, once.
    records = []
    for item in payload["result"]["list"]:
        records.append({
            "timestamp": int(item["fundingRateTimestamp"]),
            "funding_rate": float(item["fundingRate"]),
        })
    return records


def fetch_funding_history(symbol, stop_at_ms=None, category="linear"):
    """Download the funding history of a symbol, walking backwards in time.

    The API gives at most 200 records per call, so we ask for the latest page,
    then ask again with endTime just before the oldest record we received,
    until the API returns nothing.

    If stop_at_ms is given, we stop as soon as we reach records at or before
    that timestamp and only return records strictly newer than it
    (used for incremental updates: we cannot use startTime alone, because
    the docs say passing only startTime returns an error).

    Returns a list of records sorted from oldest to newest, without duplicates.
    """
    records = []
    end_time_ms = None  # None = start from "now"

    while True:
        page = fetch_funding_page(symbol, end_time_ms, category)
        if not page:
            break  # no more data: we reached the beginning of the history

        records.extend(page)
        oldest = min(record["timestamp"] for record in page)

        # Safety check: if the API ignored endTime we would loop forever.
        if end_time_ms is not None and oldest > end_time_ms:
            raise BybitAPIError("pagination is not moving backwards in time")

        if stop_at_ms is not None and oldest <= stop_at_ms:
            break  # we already have everything older than this

        end_time_ms = oldest - 1  # next page: strictly older records
        time.sleep(PAUSE_SECONDS)

    # Remove duplicates (same timestamp) and sort oldest -> newest.
    # We do not rely on the order of the API response: the docs do not state it.
    by_timestamp = {record["timestamp"]: record for record in records}
    history = sorted(by_timestamp.values(), key=lambda record: record["timestamp"])

    if stop_at_ms is not None:
        history = [record for record in history if record["timestamp"] > stop_at_ms]
    return history
