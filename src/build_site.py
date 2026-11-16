"""Build docs/index.html: interactive Plotly charts of Bybit funding rates.

Reads every data/funding_<SYMBOL>.csv written by scripts/update.py.
Run from the repository root:  python -m src.build_site
"""

from datetime import datetime, timezone
from pathlib import Path
from string import Template

import pandas as pd
import plotly.graph_objects as go

from src.metrics import add_metrics

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
OUTPUT_FILE = ROOT / "docs" / "index.html"
COLORS = {"BTCUSDT": "#f7931a", "ETHUSDT": "#627eea"}


def load_metrics():
    """Read each CSV in data/ and return {symbol: DataFrame with metrics}."""
    metrics_by_symbol = {}
    for path in sorted(DATA_DIR.glob("funding_*.csv")):
        symbol = path.stem.removeprefix("funding_")
        metrics_by_symbol[symbol] = add_metrics(pd.read_csv(path))
    return metrics_by_symbol


def empty_figure(title, y_title):
    fig = go.Figure()
    fig.update_layout(
        title=title,
        xaxis_type="date",
        yaxis_title=y_title,
        yaxis_ticksuffix="%",
        hovermode="x unified",
        template="plotly_white",
        height=420,
        margin=dict(l=60, r=20, t=60, b=40),
        legend=dict(orientation="h", y=-0.12),
    )
    return fig


def line(df, column, name, color, width, decimals, opacity=1.0):
    """One line of a chart. Values are decimals, so multiply by 100 to show percentages."""
    return go.Scatter(
        # x as short UTC strings ("2020-03-25 16:00") from the CSV.
        # Not milliseconds: Plotly.js would show those in the viewer's local time zone.
        x=df["time_utc"],
        y=df[column] * 100,
        name=name,
        mode="lines",
        line=dict(color=color, width=width),
        opacity=opacity,
        hovertemplate=f"%{{y:.{decimals}f}}%",
    )


def build_figures(metrics_by_symbol):
    funding = empty_figure("Funding rate per settlement", "% of notional")
    annualized = empty_figure("Annualized funding rate (7-day and 30-day moving averages)", "% per year")
    cumulative = empty_figure("Cumulative funding since first record", "% of notional")

    for symbol, df in metrics_by_symbol.items():
        color = COLORS.get(symbol)
        funding.add_trace(line(df, "funding_rate", symbol, color, width=1, decimals=4))
        annualized.add_trace(line(df, "annualized_ma_7d", f"{symbol} 7d MA", color, width=1, decimals=2, opacity=0.45))
        annualized.add_trace(line(df, "annualized_ma_30d", f"{symbol} 30d MA", color, width=2.5, decimals=2))
        cumulative.add_trace(line(df, "cumulative", symbol, color, width=2, decimals=2))

    return [funding, annualized, cumulative]


PAGE = Template("""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Crypto Derivatives Monitor</title>
<style>
  body { font-family: system-ui, sans-serif; max-width: 1100px; margin: 0 auto; padding: 16px; color: #222; background: #fff; }
  h1 { margin-bottom: 4px; }
  .meta { color: #666; font-size: 14px; margin-top: 0; }
  .chart { margin: 24px 0; }
  code { background: #f3f3f3; padding: 1px 4px; border-radius: 3px; }
  footer { color: #666; font-size: 13px; border-top: 1px solid #ddd; margin-top: 32px; padding-top: 12px; }
</style>
</head>
<body>
<h1>Crypto Derivatives Monitor</h1>
<p class="meta">Bybit USDT perpetuals ($symbols) &middot; funding rate history<br>
Data up to: <b>$last_record UTC</b> &middot; Page generated: $generated UTC</p>

$charts

<h2>Methodology</h2>
<ul>
  <li><b>Source:</b> Bybit public API v5, <code>GET /v5/market/funding/history</code> (category <code>linear</code>), full history downloaded by paging backwards 200 records at a time.</li>
  <li><b>Funding rate:</b> the rate paid at each settlement, as a % of position notional. Positive: longs pay shorts. Negative: shorts pay longs.</li>
  <li><b>Funding interval:</b> not assumed; measured as the time between consecutive settlements: <code>interval = t<sub>i</sub> &minus; t<sub>i-1</sub></code> (hours).</li>
  <li><b>Annualized rate</b> (simple, no compounding): <code>annualized = rate &times; 8760 / interval_hours</code>. Example: 0.01% every 8h &rarr; 0.01% &times; 1095 = 10.95% per year.</li>
  <li><b>Moving averages:</b> mean of the annualized rate over the last 7 and 30 calendar days, <code>(t &minus; N days, t]</code>. The first N days of history are left blank.</li>
  <li><b>Cumulative funding:</b> running sum of the funding rates, <code>cumulative<sub>t</sub> = rate<sub>1</sub> + &hellip; + rate<sub>t</sub></code>: the share of notional a long would have paid (a short received) holding a constant position, without compounding.</li>
</ul>

<footer>Analysis tool only, not investment advice. Data from Bybit's public API, provided as is.</footer>
</body>
</html>
""")


def build_page(metrics_by_symbol):
    figures = build_figures(metrics_by_symbol)

    # The first chart loads plotly.js from the CDN; the others reuse it.
    charts_html = []
    for i, fig in enumerate(figures):
        include_js = "cdn" if i == 0 else False
        chart = fig.to_html(full_html=False, include_plotlyjs=include_js)
        charts_html.append(f'<div class="chart">{chart}</div>')

    last_record = max(df["time"].max() for df in metrics_by_symbol.values())
    return PAGE.substitute(
        symbols=", ".join(metrics_by_symbol),
        last_record=last_record.strftime("%Y-%m-%d %H:%M"),
        generated=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
        charts="\n".join(charts_html),
    )


def main():
    metrics_by_symbol = load_metrics()
    if not metrics_by_symbol:
        raise SystemExit("No data/funding_*.csv files found: run python -m scripts.update first.")
    OUTPUT_FILE.parent.mkdir(exist_ok=True)
    OUTPUT_FILE.write_text(build_page(metrics_by_symbol), encoding="utf-8")
    print(f"Wrote {OUTPUT_FILE.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
