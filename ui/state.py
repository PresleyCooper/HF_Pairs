"""Cached data access and backtest runs for the Streamlit app.

Two cache layers keep the app fast:

1. ``CachedDownloader`` keeps each ticker's full history on disk for the day.
2. ``st.cache_data`` memoizes the loaded data and each backtest in memory,
   keyed by the (hashable) pairs and config.
"""

from __future__ import annotations

from datetime import date

import streamlit as st

from pairs_engine import BacktestConfig, BacktestResult, LoadResult, PairSpec, load_prices, run_backtest
from pairs_engine.data import warmup_start
from pairs_engine.diagnostics import PairDiagnostics, diagnose_pair
from pairs_engine.price_cache import CachedDownloader


@st.cache_resource
def _downloader() -> CachedDownloader:
    return CachedDownloader(".cache/prices")


@st.cache_data(show_spinner=False, max_entries=32)
def get_prices(tickers: tuple[str, ...], start: date, end: date, benchmark: str, beta_window: int) -> LoadResult:
    """Prices for ``tickers`` plus the benchmark, with a warm-up period."""
    return load_prices(
        list(tickers),
        warmup_start(start, beta_window),
        end,
        calendar_ticker=benchmark,
        downloader=_downloader(),
    )


@st.cache_data(show_spinner=False, max_entries=128)
def get_result(pairs: tuple[PairSpec, ...], config: BacktestConfig) -> BacktestResult:
    tickers = tuple(sorted({t for p in pairs for t in (p.long, p.short)}))
    loaded = get_prices(tickers, config.start, config.end, config.benchmark, config.beta_window)
    return run_backtest(list(pairs), config, loaded.data)


@st.cache_data(show_spinner=False, max_entries=256)
def get_diagnostics(long: str, short: str, start: date, end: date, benchmark: str, window: int) -> PairDiagnostics:
    loaded = get_prices(tuple(sorted({long, short})), start, end, benchmark, window)
    return diagnose_pair(loaded.data, long, short, start=start, end=end, window=window)


def pair_tickers(pairs: tuple[PairSpec, ...]) -> tuple[str, ...]:
    return tuple(sorted({t for p in pairs for t in (p.long, p.short)}))
