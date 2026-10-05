"""HF Pairs: an educational pairs trading backtester.

Run with:  streamlit run app.py

This file only wires things together. The engine lives in ``pairs_engine/``
and each tab lives in ``ui/tabs/``.
"""

from __future__ import annotations

import streamlit as st

from ui.pair_editor import render_pair_editor, render_save_load
from ui.sidebar import render_sidebar
from ui.state import get_prices, get_result, pair_tickers
from ui.tabs import RunContext, attribution, diagnostics, learn, overview, performance, stress

st.set_page_config(
    page_title="HF Pairs | AIO Kennesaw State",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
      .block-container { padding-top: 3.5rem; max-width: 1400px; }
      div[data-testid="stMetricValue"] { font-size: 1.6rem; font-variant-numeric: tabular-nums; }
      .app-kicker { color: #52514e; font-size: 0.85rem; letter-spacing: .06em; text-transform: uppercase; margin-bottom: 0.2rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown('<div class="app-kicker">Alternative Investments Organization · Kennesaw State University</div>',
            unsafe_allow_html=True)
st.title("Pairs Trading Backtester")
st.caption(
    "Build a long/short book from pairs trades, choose how much market exposure to keep, and see "
    "how a hedge fund would have fared. For education only, not investment advice."
)

config = render_sidebar()

with st.container(border=True):
    st.markdown("#### Portfolio of pairs")
    pairs, problems = render_pair_editor()
    render_save_load(pairs, config)

for p in problems:
    st.warning(p, icon="⚠️")
if config is None:
    st.stop()
if not pairs:
    st.info("Add at least one pair above (try the presets) to run a backtest.")
    st.stop()

pairs_t = tuple(pairs)
with st.spinner("Downloading prices and running the backtest…"):
    try:
        loaded = get_prices(pair_tickers(pairs_t), config.start, config.end, config.benchmark, config.beta_window)
        result = get_result(pairs_t, config)
        neutral = result if config.target_beta == 0 else get_result(pairs_t, config.with_target_beta(0.0))
    except ValueError as exc:
        st.error(f"Could not run the backtest: {exc}")
        st.stop()

if loaded.missing:
    st.error(
        "No data found for: **" + ", ".join(loaded.missing) + "**. Check the ticker symbols "
        "(Yahoo Finance format, e.g. BRK-B). Pairs using them are skipped."
    )
if not result.pairs:
    st.error("None of the pairs had enough price history in this window to trade.")
    st.stop()

notes = list(loaded.warnings) + list(result.warnings)
for name, n in result.sizing_notes.items():
    if n["floored"]:
        notes.append(f"{name}: a beta or volatility estimate was below the 0.1 floor on {n['floored']} "
                     "rebalance(s), so sizing used the floor instead.")
    if n["fallback"]:
        notes.append(f"{name}: estimates were missing on {n['fallback']} rebalance(s); used dollar-neutral sizing.")
if notes:
    with st.expander(f"Data & sizing notes ({len(notes)})", icon="ℹ️"):
        for n in notes:
            st.markdown(f"- {n}")

ctx = RunContext(pairs=pairs, config=config, result=result, neutral=neutral)
tabs = st.tabs(["Overview", "Performance", "Attribution", "Diagnostics", "Stress & Sensitivity", "Learn"])
with tabs[0]:
    overview.render(ctx)
with tabs[1]:
    performance.render(ctx)
with tabs[2]:
    attribution.render(ctx)
with tabs[3]:
    diagnostics.render(ctx)
with tabs[4]:
    stress.render(ctx)
with tabs[5]:
    learn.render()
