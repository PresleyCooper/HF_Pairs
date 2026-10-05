"""Sidebar: every backtest assumption, each with a tooltip.

Widget values live in ``st.session_state`` under the keys in ``DEFAULTS``.
Defaults are seeded once, and widgets are created without a ``value=``
argument. That lets a loaded JSON portfolio overwrite the settings (see
``apply_config``) without Streamlit's "default vs. session state" conflict.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import streamlit as st

from pairs_engine import BacktestConfig, RebalanceFreq

from .glossary import tip

BENCHMARKS = ["SPY", "QQQ", "IWM", "DIA"]
REBALANCE_LABELS = {
    RebalanceFreq.DAILY: "Daily",
    RebalanceFreq.WEEKLY: "Weekly",
    RebalanceFreq.MONTHLY: "Monthly",
    RebalanceFreq.NEVER: "Never (buy & hold)",
}
MIN_DATE = date(1995, 1, 1)

DEFAULTS: dict[str, Any] = {
    "target_beta": 0.0,
    "benchmark": "SPY",
    "beta_window": 60,
    "start": date(2015, 1, 1),
    "end": date.today(),
    "capital": 1_000_000,
    "leverage": 2.0,
    "rebalance": RebalanceFreq.MONTHLY,
    "tc_bps": 5.0,
    "borrow": 0.5,
    "etf_borrow": 0.25,
    "cash_rate": 2.0,
    "short_divs": True,
}


def _seed_defaults() -> None:
    for k, v in DEFAULTS.items():
        st.session_state.setdefault(k, v)


def _clamp(v: float, lo: float, hi: float) -> float:
    return min(max(v, lo), hi)


def apply_config(cfg: BacktestConfig) -> None:
    """Push a loaded config into the sidebar widgets (call from a callback)."""
    ss = st.session_state
    ss.target_beta = round(round(_clamp(cfg.target_beta, -0.5, 1.5) / 0.05) * 0.05, 2)
    ss.benchmark = cfg.benchmark if cfg.benchmark in BENCHMARKS else "SPY"
    ss.beta_window = int(round(_clamp(cfg.beta_window, 20, 250) / 5) * 5)
    ss.start = max(cfg.start, MIN_DATE)
    ss.end = min(cfg.end, date.today())
    ss.capital = int(cfg.initial_capital)
    ss.leverage = round(round(_clamp(cfg.gross_leverage, 0.5, 4.0) / 0.25) * 0.25, 2)
    ss.rebalance = cfg.rebalance
    ss.tc_bps = float(cfg.tc_bps)
    ss.borrow = cfg.borrow_rate * 100
    ss.etf_borrow = cfg.etf_borrow_rate * 100
    ss.cash_rate = cfg.cash_rate * 100
    ss.short_divs = bool(cfg.charge_short_dividends)


def render_sidebar() -> BacktestConfig | None:
    """Draw the sidebar and return the resulting config (None if invalid)."""
    _seed_defaults()
    sb = st.sidebar
    sb.markdown("### Market exposure")
    target_beta = sb.slider("Target portfolio beta", min_value=-0.5, max_value=1.5, step=0.05,
                            help=tip("target_beta"), key="target_beta")
    sb.caption("0 = market neutral · 0.3 = typical 'low net' fund · 1.0 = moves like the index")
    benchmark = sb.selectbox("Benchmark", BENCHMARKS, help=tip("benchmark"), key="benchmark")
    beta_window = sb.slider("Rolling beta window (trading days)", 20, 250, step=5,
                            help=tip("beta_window"), key="beta_window")

    sb.markdown("### Backtest window")
    c1, c2 = sb.columns(2)
    start = c1.date_input("Start", min_value=MIN_DATE, max_value=date.today(), key="start")
    end = c2.date_input("End", min_value=MIN_DATE, max_value=date.today(), key="end")

    sb.markdown("### Book")
    capital = sb.number_input("Starting capital ($)", min_value=10_000, step=100_000, format="%d", key="capital")
    leverage = sb.slider("Gross leverage (pair book)", 0.5, 4.0, step=0.25,
                         help=tip("gross_leverage"), key="leverage")
    rebalance = sb.selectbox("Rebalance frequency", list(REBALANCE_LABELS), format_func=REBALANCE_LABELS.get,
                             help=tip("rebalance"), key="rebalance")

    sb.markdown("### Costs & financing")
    tc_bps = sb.number_input("Transaction cost (bps per $ traded)", 0.0, 100.0, step=0.5,
                             help=tip("tc"), key="tc_bps")
    borrow = sb.number_input("Stock borrow fee (% / yr on shorts)", 0.0, 50.0, step=0.25,
                             help=tip("borrow"), key="borrow")
    etf_borrow = sb.number_input("ETF borrow fee (% / yr, short overlay)", 0.0, 10.0, step=0.05,
                                 help=tip("overlay"), key="etf_borrow")
    cash_rate = sb.number_input("Cash interest rate (% / yr)", 0.0, 15.0, step=0.25,
                                help=tip("cash_rate"), key="cash_rate")
    short_divs = sb.toggle("Charge dividends to the short leg", help=tip("short_dividends"), key="short_divs")

    if end <= start:
        sb.error("End date must be after the start date.")
        return None
    return BacktestConfig(
        start=start, end=end, initial_capital=float(capital), gross_leverage=float(leverage),
        rebalance=rebalance, tc_bps=float(tc_bps), borrow_rate=borrow / 100,
        etf_borrow_rate=etf_borrow / 100, cash_rate=cash_rate / 100,
        charge_short_dividends=short_divs, benchmark=benchmark,
        beta_window=int(beta_window), target_beta=float(target_beta),
    )
