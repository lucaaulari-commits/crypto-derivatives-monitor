# crypto-derivatives-monitor

[![tests](https://github.com/lucaaulari-commits/crypto-derivatives-monitor/actions/workflows/tests.yml/badge.svg)](https://github.com/lucaaulari-commits/crypto-derivatives-monitor/actions/workflows/tests.yml)

A static web page with the full funding rate history of Bybit USDT perpetuals **BTCUSDT** and **ETHUSDT**: funding per settlement, annualized funding (7-day and 30-day moving averages) and cumulative funding. The date of the latest stored record is shown at the top of the page; above the charts, a small box shows the latest funding rate fetched live from Bybit by the visitor's browser.

**Live demo:** https://lucaaulari-commits.github.io/crypto-derivatives-monitor/

## Run it locally

Requires Python 3.11+.

```bash
git clone https://github.com/lucaaulari-commits/crypto-derivatives-monitor.git && cd crypto-derivatives-monitor
pip install -r requirements.txt
python -m scripts.update
```

The last command downloads any new funding records into `data/` and rebuilds `docs/index.html`; open that file in a browser. Run the tests with `python -m pytest`.

## How it works

| File | Role |
|---|---|
| `src/bybit_client.py` | Calls `GET /v5/market/funding/history` (public, no API key), paging backwards 200 records at a time |
| `scripts/update.py` | Appends only new records to `data/funding_<SYMBOL>.csv`, without duplicates, then rebuilds the page |
| `src/metrics.py` | Funding interval, annualized rate, moving averages, cumulative funding |
| `src/build_site.py` | Writes `docs/index.html` with Plotly charts (served by GitHub Pages) |
| `tests/test_metrics.py` | pytest tests on small hand-made data |
| `scripts/update_and_push.sh` | Runs the update locally and commits/pushes only if there are new records |
| `.github/workflows/` | `tests.yml` runs pytest on every push; `update.yml` is the same update on GitHub, manual only (see below) |

### Why the data is updated from a local machine

Bybit answers `403 Forbidden` to GitHub-hosted runners (geo-restriction on their cloud IPs), so the scheduled GitHub Actions update cannot reach the API. The data is therefore refreshed by running `./scripts/update_and_push.sh` from a machine where the API is reachable. `update.yml` is kept as a manual workflow to re-test this.

## Methodology

All rates are decimals in the code (0.0001 = 0.01%). Positive funding: longs pay shorts.

- **Funding interval** is measured, not assumed (Bybit uses e.g. 4h or 8h depending on the symbol): `interval_hours = (t_i - t_(i-1)) / 3,600,000 ms`.
- **Annualized rate**, simple, no compounding: `annualized = funding_rate × 8760 / interval_hours`. Example: 0.01% every 8h → 0.01% × 1095 = 10.95% per year.
- **Moving averages**: mean of the annualized rate over the last 7 and 30 calendar days, window `(t − N days, t]`. The first N days of history are left blank.
- **Cumulative funding**: `cumulative_t = rate_1 + … + rate_t`, the share of notional a long would have paid (a short received) holding a constant position.

## Data limitations

- One exchange and two symbols only: Bybit funding is not the whole market.
- Data is used as returned by Bybit's API and not cross-checked with other sources. History starts 2020-03-25 (BTCUSDT) and 2020-10-21 (ETHUSDT).
- The interval is inferred from consecutive records: if a record were missing, the interval for that point would look doubled and its annualized rate halved.
- Annualized and cumulative figures ignore compounding, price changes, fees and the position's actual notional at each settlement.
- Charts are not updated automatically (see above) and can be behind the live market; check the "stored data up to" date at the top of the page.
- The live box calls Bybit from the visitor's browser, so it is hidden where Bybit is not reachable (e.g. geo-restricted countries). Its two formulas (interval, annualized) are repeated in JavaScript and not covered by the pytest tests.
- The page loads plotly.js from its CDN.

## Disclaimer

This is an analysis tool for educational purposes. It is **not investment advice** and must not be used as the sole basis for trading decisions.

## License

[MIT](LICENSE)
