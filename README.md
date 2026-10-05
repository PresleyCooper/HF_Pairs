# HF Pairs: Educational Pairs Trading Backtester

Built for the **Alternative Investments Organization at Kennesaw State University**.

Enter a list of pairs trades (for example, long KO and short PEP) and the app backtests them as one long/short equity portfolio. A **target beta slider** sets how much market exposure the book carries. Diagnostics and explanations throughout show students how real long/short hedge funds build, hedge, and stress-test a pairs book.

> 🚧 Under construction. The engine and the core UI (Overview and Performance tabs) work. Diagnostics, the Learn tab and stress tests are coming next.

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux
pip install -r requirements.txt
```

## Run the app

```bash
streamlit run app.py
```

The first run downloads full price history for each ticker from Yahoo Finance and caches it in `.cache/prices/` for the rest of the day. After that, changing dates and settings is instant.

## Run the tests

```bash
pytest -q
```

The tests run on synthetic price data and never touch the network.

## Project layout

| Path | What it is |
| --- | --- |
| `pairs_engine/` | The backtest engine: pure Python with no UI code, so it can be reused or tested on its own |
| `pairs_engine/config.py` | `PairSpec` (one pair) and `BacktestConfig` (all assumptions) |
| `pairs_engine/data.py` | yfinance loader, calendar alignment, short-history warnings |
| `pairs_engine/beta.py` | Rolling, point-in-time beta, volatility and correlation |
| `pairs_engine/sizing.py` | Dollar-neutral, beta-neutral and volatility-matched leg sizing |
| `pairs_engine/costs.py` | Transaction cost, borrow fee, cash interest |
| `pairs_engine/backtest.py` | The daily simulation loop and beta overlay |
| `pairs_engine/analytics.py` | Tear-sheet stats, drawdowns, P&L attribution |
| `pairs_engine/presets.py` | Example pairs with a one-line rationale each |
| `pairs_engine/price_cache.py` | Daily on-disk parquet cache of full price histories |
| `app.py` | Streamlit entry point (wiring only) |
| `ui/` | Sidebar, pair editor, chart builders, glossary text, one module per tab |
| `tests/` | pytest suite, including a no-lookahead test |

## How the engine works (short version)

- **Timing:** at the close of each day, positions first earn that day's return. Then, on rebalance days, new targets are set using only data up to that close. Nothing looks ahead, and `tests/test_no_lookahead.py` checks this by corrupting future prices and confirming the past doesn't change.
- **Sizing:** each pair gets `gross leverage × NAV × weight` in gross dollars, split between the legs by the sizing method you choose.
- **Beta overlay:** a position in the benchmark ETF equal to `(target beta − book beta) × NAV`. It sits outside the gross leverage budget.
- **Costs:** transaction costs in bps on every dollar traded, borrow fees on short notional, and interest on cash plus short proceeds, all accrued actual/365.
- **Dividends:** longs earn total return. Shorts pay total return, meaning they pay the dividend, unless you switch that off to see the effect.
