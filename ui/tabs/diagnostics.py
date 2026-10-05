"""Diagnostics tab: is each pair actually a pair?"""

from __future__ import annotations

import math

import pandas as pd
import streamlit as st

from pairs_engine.diagnostics import coint_verdict, half_life_verdict
from pairs_engine.presets import PRESETS

from .. import charts
from ..state import get_diagnostics
from . import RunContext

EXPLAIN = {
    "ratio": (
        "**Price ratio with z-score bands.** The line is ln(long price ÷ short price). If the "
        "two stocks really move together, this ratio wanders around a stable level instead of "
        "trending. The shaded bands are ±1σ and ±2σ around its trailing mean.\n\n"
        "*Why a PM cares:* a classic relative-value trade buys the pair when the ratio is "
        "stretched (z-score below −2) and takes profit as it reverts. A ratio that trends "
        "for years means one company is steadily winning, and no hedge fixes that."
    ),
    "zscore": (
        "**Z-score** = how many standard deviations the ratio is from its trailing mean, "
        "using only past data. ±2 is a common entry signal and 0 a common exit.\n\n"
        "*Why a PM cares:* it turns 'this looks cheap' into a number that can be compared "
        "across pairs and sized consistently. Z-scores that keep hitting ±3 or ±4 are a "
        "warning that the relationship is breaking, not an extra-good opportunity."
    ),
    "corr": (
        "**Rolling correlation** of the two stocks' daily returns. Above about 0.7 is typical "
        "for a good same-industry pair.\n\n"
        "*Why a PM cares:* the hedge only works while the legs move together. Watch for "
        "correlation collapsing during stress. That is exactly when you need the hedge most."
    ),
    "hedge": (
        "**OLS hedge ratio** is the slope from regressing ln(long) on ln(short) over the "
        "whole window. 1.2 means the long has moved about 1.2% for every 1% in the short. "
        "**R²** is how much of the long's price path the short explains.\n\n"
        "*Why a PM cares:* it suggests how many dollars of short you need per dollar of long. "
        "It is fitted on the full period, though, so it uses hindsight."
    ),
    "coint": (
        "**Engle-Granger cointegration test.** It asks whether the OLS spread (ln long − hedge "
        "ratio × ln short) is stationary, i.e. tends to return to a fixed level. A p-value "
        "below 0.05 is the usual bar for 'yes'.\n\n"
        "*Why a PM cares:* correlation says the stocks move together *day to day*. "
        "Cointegration says their *prices* stay tied together over time. Two stocks can be "
        "90% correlated and still drift apart forever. Note: this is an in-sample test, and "
        "pairs that pass it in one period often fail it in the next."
    ),
    "half_life": (
        "**Half-life of mean reversion**: how many trading days it typically takes for a gap "
        "in the spread to close halfway, from an AR(1) fit of the spread.\n\n"
        "*Why a PM cares:* it sets the holding period and tells you whether costs will eat "
        "the edge. A 5-day half-life suits an active trading book. A 300-day half-life means "
        "you could wait a year to be proven right, while paying borrow and facing "
        "redemptions the whole time."
    ),
}


def _fmt(x: float, spec: str = ".2f") -> str:
    return f"{x:{spec}}" if isinstance(x, float) and math.isfinite(x) else ("∞" if x == float("inf") else "–")


def _summary_table(ctx: RunContext, window: int) -> pd.DataFrame:
    cfg = ctx.config
    rows = []
    for p in ctx.result.pairs:
        try:
            d = get_diagnostics(p.long, p.short, cfg.start, cfg.end, cfg.benchmark, window)
        except ValueError:
            continue
        rows.append({
            "Pair": p.label,
            "Return corr.": _fmt(d.return_corr),
            "Hedge ratio": _fmt(d.hedge_ratio),
            "R²": _fmt(d.r_squared),
            "Coint. p-value": _fmt(d.coint_pvalue, ".3f"),
            "Cointegration": coint_verdict(d.coint_pvalue),
            "Half-life (days)": _fmt(d.half_life, ".0f"),
            "Mean reversion": half_life_verdict(d.half_life),
            "Z-score today": _fmt(float(d.zscore.dropna().iloc[-1]) if d.zscore.notna().any() else float("nan")),
        })
    return pd.DataFrame(rows)


def render(ctx: RunContext) -> None:
    cfg = ctx.config
    st.markdown(
        "Before a PM puts on a pair, they check whether the two stocks really belong together. "
        "These diagnostics are measured over your backtest window. Pick a pair below for detail."
    )
    window = st.slider("Window for bands, z-score and rolling correlation (trading days)",
                       20, 252, cfg.beta_window, step=5, key="diag_window")

    with st.spinner("Running diagnostics…"):
        table = _summary_table(ctx, window)
    st.markdown("#### All pairs at a glance")
    st.table(table.set_index("Pair") if len(table) else table)

    names = [p.label for p in ctx.result.pairs]
    choice = st.selectbox("Pair to inspect", names, key="diag_pair")
    pair = ctx.result.pairs[names.index(choice)]
    try:
        d = get_diagnostics(pair.long, pair.short, cfg.start, cfg.end, cfg.benchmark, window)
    except ValueError as exc:
        st.warning(str(exc))
        return

    preset = next((p for p in PRESETS if {p.long, p.short} == {pair.long, pair.short}), None)
    if preset:
        st.info(f"**{preset.sector}.** {preset.rationale}", icon="💡")

    c = st.columns(5)
    c[0].metric("Return correlation", _fmt(d.return_corr), border=True, help=EXPLAIN["corr"])
    c[1].metric("OLS hedge ratio", _fmt(d.hedge_ratio), f"R² {d.r_squared:.2f}", delta_color="off",
                delta_arrow="off", border=True, help=EXPLAIN["hedge"])
    c[2].metric("Cointegration p-value", _fmt(d.coint_pvalue, ".3f"), coint_verdict(d.coint_pvalue),
                delta_color="green" if d.coint_pvalue < 0.05 else ("orange" if d.coint_pvalue < 0.10 else "red"),
                delta_arrow="off", border=True, help=EXPLAIN["coint"])
    c[3].metric("Half-life (days)", _fmt(d.half_life, ".0f"), half_life_verdict(d.half_life),
                delta_color="off", delta_arrow="off", border=True, help=EXPLAIN["half_life"])
    z_now = d.zscore.dropna()
    c[4].metric("Z-score today", _fmt(float(z_now.iloc[-1])) if len(z_now) else "–", border=True,
                help=EXPLAIN["zscore"])

    charts.show(charts.band_chart(d.log_ratio, d.ratio_mean, d.ratio_std, f"ln({pair.long} / {pair.short})",
                          f"Price ratio {pair.long} / {pair.short} with trailing ±1σ / ±2σ bands"))
    with st.expander("What am I looking at?"):
        st.markdown(EXPLAIN["ratio"])

    left, right = st.columns(2)
    with left:
        charts.show(charts.line_chart([("Z-score", d.zscore, charts.PORTFOLIO, "solid")],
                              title=f"Z-score (trailing {window}-day)", yfmt=".1f", height=320,
                              hline=(0.0, "Mean")))
        with st.expander("What is a z-score?"):
            st.markdown(EXPLAIN["zscore"])
    with right:
        charts.show(charts.line_chart([("Correlation", d.rolling_corr, charts.PORTFOLIO, "solid")],
                              title=f"Rolling {window}-day correlation of daily returns", yfmt=".2f",
                              height=320, hline=(0.0, "Uncorrelated")))
        with st.expander("Why does correlation matter?"):
            st.markdown(EXPLAIN["corr"])

    charts.show(charts.line_chart([("OLS spread", d.spread, charts.PORTFOLIO, "solid")],
                          title=f"Cointegration spread: ln({pair.long}) − {d.hedge_ratio:.2f} × ln({pair.short}) "
                                "(full-sample fit)",
                          yfmt=".2f", height=320, hline=(0.0, "Long-run equilibrium")))
    cols = st.columns(3)
    for col, key, title in zip(cols, ("hedge", "coint", "half_life"),
                               ("Hedge ratio & R²", "Cointegration test", "Half-life")):
        with col.expander(title):
            st.markdown(EXPLAIN[key])
    st.caption(
        "⚠️ The hedge ratio, cointegration test and half-life are fitted on the whole window, so they "
        "use hindsight. The bands, z-score and rolling correlation use only past data. The backtest "
        "itself never uses the full-sample numbers."
    )
