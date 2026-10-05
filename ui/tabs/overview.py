"""Overview tab: headline numbers, equity curve and the side-by-side stats table."""

from __future__ import annotations

import streamlit as st

from pairs_engine.analytics import daily_report, result_stats, summary_stats

from .. import charts
from ..formatting import beta_label, fmt_value, stats_table
from ..glossary import GLOSSARY, STAT_TIPS, tip
from . import RunContext


def render(ctx: RunContext) -> None:
    res, neu, cfg = ctx.result, ctx.neutral, ctx.config
    stats = result_stats(res)
    neutral_stats = result_stats(neu)
    bench_stats = summary_stats(res.bench_returns, res.bench_returns, cfg.cash_rate)

    # ---- Headline metrics ----
    cols = st.columns(5)
    headline = [
        ("Total return", "pct", None),
        ("CAGR", "pct", None),
        ("Sharpe ratio", "num", "sharpe"),
        ("Max drawdown", "pct", "drawdown"),
        ("Realized beta", "num", "beta"),
    ]
    for col, (name, kind, key) in zip(cols, headline):
        delta = None
        if not ctx.is_neutral:
            d = stats[name] - neutral_stats[name]
            delta = f"{fmt_value(d, kind)} vs neutral"
        col.metric(name, fmt_value(stats[name], kind), delta=delta,
                   delta_color="off" if name in ("Realized beta",) else "normal",
                   help=tip(key) if key else None, border=True)

    # ---- Equity curves ----
    cap = cfg.initial_capital
    bench_nav = cap * (1 + res.bench_returns).cumprod()
    curves = [(f"Portfolio ({beta_label(cfg.target_beta)})", res.nav, charts.PORTFOLIO, "solid")]
    if not ctx.is_neutral:
        curves.append(("Market neutral (β = 0)", neu.nav, charts.NEUTRAL, "solid"))
    curves.append((f"{cfg.benchmark} (buy & hold)", bench_nav, charts.BENCH, "dot"))
    charts.show(charts.equity_chart(curves, f"Growth of ${cap:,.0f}"))

    # ---- Stats table: full width, every row and column visible without scrolling ----
    st.markdown("#### Summary statistics")
    columns = {f"Your book ({beta_label(cfg.target_beta)})": stats}
    if not ctx.is_neutral:
        columns["Market neutral (β = 0)"] = neutral_stats
    columns[f"{cfg.benchmark}"] = bench_stats
    st.table(stats_table(columns).rename_axis("Statistic"))
    if ctx.is_neutral:
        st.caption("Move the **target beta** slider to compare your book against its market-neutral version.")

    # ---- Explanations, below the table in a grid ----
    st.markdown("#### What the numbers mean")
    explainers = [(stat, GLOSSARY[key]) for stat, key in STAT_TIPS.items()]
    explainers.append(("Gross vs net exposure", GLOSSARY["gross_net"]))
    explainers.append((
        "Why compare to a market-neutral version?",
        "Both columns hold the *same pairs*. The only difference is the size of the benchmark "
        "overlay. Any gap in return, volatility or drawdown between them comes from the market "
        "exposure you chose, not from stock picking. If most of your return disappears at β = 0, "
        "your 'alpha' was really beta.",
    ))
    grid = st.columns(3)
    for i, (title, body) in enumerate(explainers):
        with grid[i % 3].expander(title):
            st.markdown(body)

    st.download_button(
        "Download daily results (CSV)",
        data=daily_report(res).to_csv().encode("utf-8"),
        file_name=f"hf_pairs_daily_{cfg.start:%Y%m%d}_{cfg.end:%Y%m%d}.csv",
        mime="text/csv",
        help="NAV, returns, betas, exposures, costs and net P&L by pair for every trading day.",
    )
