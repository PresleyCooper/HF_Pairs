"""Sidebar: every backtest assumption, each with a tooltip."""

from __future__ import annotations

from datetime import date

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


def render_sidebar() -> BacktestConfig | None:
    """Draw the sidebar and return the resulting config (None if invalid)."""
    sb = st.sidebar
    sb.markdown("### Market exposure")
    target_beta = sb.slider(
        "Target portfolio beta", min_value=-0.5, max_value=1.5, value=0.0, step=0.05,
        help=tip("target_beta"), key="target_beta",
    )
    benchmark = sb.selectbox("Benchmark", BENCHMARKS, index=0, help=tip("benchmark"), key="benchmark")
    beta_window = sb.slider(
        "Rolling beta window (trading days)", 20, 252, 60, step=5,
        help=tip("beta_window"), key="beta_window",
    )

    sb.markdown("### Backtest window")
    c1, c2 = sb.columns(2)
    start = c1.date_input("Start", value=date(2015, 1, 1), min_value=date(1995, 1, 1),
                          max_value=date.today(), key="start")
    end = c2.date_input("End", value=date.today(), min_value=date(1995, 1, 2),
                        max_value=date.today(), key="end")

    sb.markdown("### Book")
    capital = sb.number_input("Starting capital ($)", min_value=10_000, value=1_000_000,
                              step=100_000, format="%d", key="capital")
    leverage = sb.slider("Gross leverage (pair book)", 0.5, 4.0, 2.0, step=0.25,
                         help=tip("gross_leverage"), key="leverage")
    rebalance = sb.selectbox(
        "Rebalance frequency", list(REBALANCE_LABELS), index=2,
        format_func=REBALANCE_LABELS.get, help=tip("rebalance"), key="rebalance",
    )

    sb.markdown("### Costs & financing")
    tc_bps = sb.number_input("Transaction cost (bps per $ traded)", 0.0, 100.0, 5.0, step=0.5,
                             help=tip("tc"), key="tc_bps")
    borrow = sb.number_input("Stock borrow fee (% / yr on shorts)", 0.0, 50.0, 0.5, step=0.25,
                             help=tip("borrow"), key="borrow")
    etf_borrow = sb.number_input("ETF borrow fee (% / yr, short overlay)", 0.0, 10.0, 0.25,
                                 step=0.05, help=tip("overlay"), key="etf_borrow")
    cash_rate = sb.number_input("Cash interest rate (% / yr)", 0.0, 15.0, 2.0, step=0.25,
                                help=tip("cash_rate"), key="cash_rate")
    short_divs = sb.toggle("Charge dividends to the short leg", value=True,
                           help=tip("short_dividends"), key="short_divs")

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
