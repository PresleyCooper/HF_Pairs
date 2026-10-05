"""Stress & Sensitivity tab: historical crisis windows and the Sharpe-vs-beta curve."""

from __future__ import annotations

import math

import pandas as pd
import streamlit as st

from pairs_engine.scenarios import SCENARIOS, scenario_config, worst_pair

from .. import charts
from ..charts import money
from ..formatting import md_money
from ..formatting import fmt_value
from ..state import get_scenario, get_sweep
from . import RunContext

PLOT_CFG = {"displaylogo": False}


def _stress_section(ctx: RunContext) -> None:
    cfg = ctx.config
    st.markdown("#### How would this book have handled a crisis?")
    st.caption(
        "Each window re-runs your exact pairs and settings, whatever dates you picked in the sidebar. "
        "Pairs whose stocks did not trade yet are left out."
    )
    pairs_t = tuple(ctx.pairs)
    outcomes = []
    with st.spinner("Running stress windows…"):
        for i in range(len(SCENARIOS)):
            # Normalise dates so moving the sidebar dates doesn't re-run the stress tests.
            outcomes.append(get_scenario(pairs_t, scenario_config(cfg, SCENARIOS[i]), i))

    rows, bars = [], {}
    for o in outcomes:
        sc = o.scenario
        short = sc.name.split(" (")[0]
        if not o.ok:
            rows.append({"Scenario": sc.name, "Dates": f"{sc.start:%b %d, %Y} – {sc.end:%b %d, %Y}",
                         "Your book": "n/a", "Market neutral": "n/a", cfg.benchmark: "n/a",
                         "Book max drawdown": "n/a", "Note": o.error or "No data"})
            bars[short] = [math.nan, math.nan, math.nan]
            continue
        rows.append({
            "Scenario": sc.name,
            "Dates": f"{sc.start:%b %d, %Y} – {sc.end:%b %d, %Y}",
            "Your book": fmt_value(o.stats["Total return"], "pct"),
            "Market neutral": fmt_value(o.neutral_stats["Total return"], "pct"),
            cfg.benchmark: fmt_value(o.bench_stats["Total return"], "pct"),
            "Book max drawdown": fmt_value(o.stats["Max drawdown"], "pct"),
            "Note": ("Skipped: " + ", ".join(o.skipped)) if o.skipped else "",
        })
        bars[short] = [o.stats["Total return"], o.neutral_stats["Total return"], o.bench_stats["Total return"]]

    names = [f"Your book (β {cfg.target_beta:+.2f})", "Market neutral (β 0)", cfg.benchmark]
    colors = [charts.PORTFOLIO, charts.NEUTRAL, charts.BENCH]
    if ctx.is_neutral:
        names, colors = [names[0], names[2]], [colors[0], colors[2]]
        bars = {k: [v[0], v[2]] for k, v in bars.items()}
    bar_df = pd.DataFrame.from_dict(bars, orient="index", columns=names)
    st.plotly_chart(charts.grouped_bar(bar_df, colors, "Total return during each stress window"),
                    width="stretch", config=PLOT_CFG)
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")

    for o in outcomes:
        with st.expander(o.scenario.name):
            st.markdown(o.scenario.description)
            if not o.ok:
                st.warning(o.error or "No data for this window.")
                continue
            res = o.result
            bench_nav = cfg.initial_capital * (1 + res.bench_returns).cumprod()
            curves = [("Your book", res.nav, charts.PORTFOLIO, "solid")]
            if not ctx.is_neutral:
                curves.append(("Market neutral", o.neutral.nav, charts.NEUTRAL, "solid"))
            curves.append((cfg.benchmark, bench_nav, charts.BENCH, "dot"))
            left, right = st.columns([3, 2])
            left.plotly_chart(charts.equity_chart(curves, "Equity during the window", height=320),
                              width="stretch", config=PLOT_CFG)
            pnl = res.pair_pnl().sum()
            right.plotly_chart(charts.bar_chart(pnl, "Net P&L by pair"), width="stretch", config=PLOT_CFG)
            name, val = worst_pair(res)
            st.markdown(f"Worst pair: **{name}** ({md_money(val)}). Realized beta during the window: "
                        f"**{o.stats['Realized beta']:.2f}** against a target of {cfg.target_beta:+.2f}.")
            if o.skipped:
                st.caption("Not in the book for this window: " + ", ".join(o.skipped))


def _sensitivity_section(ctx: RunContext) -> None:
    cfg = ctx.config
    st.markdown("#### Sensitivity: what does the beta slider actually buy you?")
    st.caption(
        "The same pairs, costs and dates, re-run at every target beta from −0.5 to +1.5. Only the size "
        "of the benchmark overlay changes, so these curves show what market exposure alone did."
    )
    with st.spinner("Running 21 backtests…"):
        # Keyed on beta 0 so dragging the slider doesn't re-run all 21 backtests.
        sweep = get_sweep(tuple(ctx.pairs), cfg.with_target_beta(0.0))
    sharpe = sweep["Sharpe ratio"].rename("Sharpe ratio")
    st.plotly_chart(charts.sweep_chart(sweep.index, sharpe, cfg.target_beta, "Sharpe ratio vs target beta",
                                       ".2f", height=360),
                    width="stretch", config=PLOT_CFG)
    c1, c2 = st.columns(2)
    c1.plotly_chart(charts.sweep_chart(sweep.index, sweep["CAGR"].rename("CAGR"), cfg.target_beta,
                                       "CAGR vs target beta", ".1%", color=charts.CATEGORICAL[2]),
                    width="stretch", config=PLOT_CFG)
    c2.plotly_chart(charts.sweep_chart(sweep.index, sweep["Max drawdown"].rename("Max drawdown"),
                                       cfg.target_beta, "Max drawdown vs target beta", ".0%",
                                       color=charts.CATEGORICAL[7]),
                    width="stretch", config=PLOT_CFG)
    best = float(sharpe.idxmax())
    st.markdown(
        f"Over this window the highest Sharpe came at a target beta of **{best:+.1f}** "
        f"(Sharpe {sharpe.max():.2f}, against {sharpe.loc[0.0]:.2f} when market neutral). "
        "Remember that this is hindsight: the best beta depends on what the market did. A fund "
        "that sells itself as market neutral but quietly runs β = 0.5 is selling beta at alpha prices."
    )
    with st.expander("Show the numbers"):
        table = sweep.copy()
        for c in table.columns:
            kind = "pct" if c in ("CAGR", "Annualized volatility", "Max drawdown") else "num"
            table[c] = table[c].map(lambda v, k=kind: fmt_value(v, k))
        table.index = [f"{b:+.1f}" for b in table.index]
        st.dataframe(table, width="stretch")


def render(ctx: RunContext) -> None:
    _stress_section(ctx)
    st.divider()
    _sensitivity_section(ctx)
