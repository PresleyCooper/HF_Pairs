"""Performance tab: drawdowns, beta tracking, correlation, exposures, per-pair curves."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from pairs_engine.analytics import drawdown, pair_returns, realized_rolling_beta, realized_rolling_corr

from .. import charts
from ..formatting import beta_label
from ..glossary import tip
from . import RunContext

PLOT_CFG = {"displaylogo": False}


def render(ctx: RunContext) -> None:
    res, neu, cfg = ctx.result, ctx.neutral, ctx.config
    window = cfg.beta_window

    # ---- Drawdown ----
    bench_nav = (1 + res.bench_returns).cumprod()
    dd = [(f"Portfolio ({beta_label(cfg.target_beta)})", drawdown(res.nav), charts.PORTFOLIO, "solid")]
    if not ctx.is_neutral:
        dd.append(("Market neutral (β = 0)", drawdown(neu.nav), charts.NEUTRAL, "solid"))
    dd.append((cfg.benchmark, drawdown(bench_nav), charts.BENCH, "dot"))
    st.plotly_chart(charts.drawdown_chart(dd), width="stretch", config=PLOT_CFG)

    # ---- Beta: target vs what the model expected vs what actually happened ----
    st.markdown("#### Did the hedge hold?", help=tip("overlay"))
    realized = realized_rolling_beta(res)
    st.plotly_chart(
        charts.line_chart(
            [
                ("Ex-ante beta (model estimate after hedging)", res.total_beta, charts.NEUTRAL, "solid"),
                (f"Realized beta (trailing {window}-day regression)", realized, charts.PORTFOLIO, "solid"),
            ],
            title=f"Portfolio beta to {cfg.benchmark}",
            yfmt=".2f", height=360, hline=(cfg.target_beta, f"Target {cfg.target_beta:+.2f}"),
        ),
        width="stretch", config=PLOT_CFG,
    )
    tracking = (realized - cfg.target_beta).abs().dropna()
    if len(tracking):
        st.caption(
            f"**Ex-ante** beta is what the model believed the book's beta was, using betas estimated "
            f"from past data. It snaps back to target at each rebalance and drifts in between. "
            f"**Realized** beta is measured afterwards from the portfolio's actual returns. The gap is "
            f"estimation error: betas change. Over this backtest, realized beta was within ±0.10 of "
            f"target **{(tracking <= 0.10).mean():.0%}** of the time, and the largest miss was "
            f"**{tracking.max():.2f}**."
        )

    # ---- Correlation ----
    corr = realized_rolling_corr(res)
    st.plotly_chart(
        charts.line_chart(
            [(f"Rolling {window}-day correlation to {cfg.benchmark}", corr, charts.PORTFOLIO, "solid")],
            title="Correlation to the market", yfmt=".2f", height=300, hline=(0.0, "Uncorrelated"),
        ),
        width="stretch", config=PLOT_CFG,
    )

    # ---- Exposures ----
    st.markdown("#### Exposure over time", help=tip("gross_net"))
    legs = res.slots.set_index("slot")["leg"]
    pos = res.positions
    long_ = pos.loc[:, (legs == "long").to_numpy()].sum(axis=1) / res.nav
    short_ = -pos.loc[:, (legs == "short").to_numpy()].sum(axis=1) / res.nav
    overlay = pos.loc[:, (legs == "overlay").to_numpy()].sum(axis=1) / res.nav
    net = long_ - short_ + overlay
    st.plotly_chart(
        charts.line_chart(
            [
                ("Long stocks", long_, charts.CATEGORICAL[0], "solid"),
                ("Short stocks (plotted negative)", -short_, charts.CATEGORICAL[1], "solid"),
                (f"{cfg.benchmark} overlay (+ long / − short)", overlay, charts.CATEGORICAL[2], "solid"),
                ("Net (long − short + overlay)", net, charts.REFERENCE, "dot"),
            ],
            title="Exposure as % of NAV", yfmt=".0%", height=340,
        ),
        width="stretch", config=PLOT_CFG,
    )
    last = res.nav.index[-1]
    c = st.columns(4)
    c[0].metric("Gross (pairs)", f"{long_.loc[last] + short_.loc[last]:.0%}", border=True)
    c[1].metric("Net stock exposure", f"{long_.loc[last] - short_.loc[last]:+.0%}", border=True)
    c[2].metric("Overlay", f"{overlay.loc[last]:+.0%}", border=True)
    c[3].metric("Ex-ante beta", f"{res.total_beta.loc[last]:+.2f}", border=True)

    # ---- Each pair on its own ----
    if res.pair_names:
        pr = pair_returns(res)
        curves = (1 + pr).cumprod()
        st.plotly_chart(
            charts.pair_lines(curves, "Each pair on its own: growth of $1 of allocated capital", yfmt="$.2f"),
            width="stretch", config=PLOT_CFG,
        )
        st.caption(
            "Each curve is one pair's net P&L (after trading and borrow costs, before cash interest) "
            f"divided by the capital backing it, i.e. its gross ÷ {cfg.gross_leverage:g}x leverage. "
            "Pairs are shown without the beta overlay, so they reflect the pair's own residual beta."
        )
