"""Attribution tab: which pairs and which legs made or lost money, and what went wrong."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from pairs_engine import OVERLAY
from pairs_engine.analytics import drawdown_breakdown, leg_attribution, pair_attribution

from .. import charts
from ..charts import money
from ..formatting import md_money
from ..glossary import tip
from . import RunContext

PLOT_CFG = {"displaylogo": False}


def _money_table(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for c in out.columns:
        if c.startswith("Contribution"):
            out[c] = out[c].map(lambda v: f"{v:+.1%}")
        else:
            out[c] = out[c].map(money)
    return out


def _legs_section(ctx: RunContext) -> None:
    res = ctx.result
    st.markdown("#### Where did the money come from?", help=tip("gross_net"))
    legs = leg_attribution(res)
    left, right = st.columns([3, 2])
    with left:
        st.plotly_chart(charts.bar_chart(legs, "Net P&L by source", sort=False),
                        width="stretch", config=PLOT_CFG)
    with right:
        spread = legs["Long legs"] + legs["Short legs"]
        costs = legs["Trading costs"] + legs["Borrow costs"]
        def verb(x: float, gain: str = "made", loss: str = "lost") -> str:
            return f"{gain if x >= 0 else loss} **{md_money(abs(x))}**"

        st.markdown(
            f"- **Long legs** {verb(legs['Long legs'])} and **short legs** {verb(legs['Short legs'])}.\n"
            f"- Together that is **{md_money(spread)}**: the stock-selection result, i.e. whether "
            "your longs beat your shorts.\n"
            f"- The **{ctx.config.benchmark} overlay** {verb(legs['Beta overlay'], 'added', 'cost')}. "
            "This is pure market exposure, not skill.\n"
            f"- **Costs** (trading + borrow) took **{md_money(abs(costs))}**, and **cash interest** "
            f"{verb(legs['Cash interest'], 'added', 'cost')}."
        )
        with st.expander("Why do the short legs usually lose money?"):
            st.markdown(
                "Stocks rise over time, so in a rising market the short side of almost every pair "
                "loses money on its own. That is expected. A pairs book makes money when the longs "
                "rise *more* than the shorts, or fall less. Judge the pair by long + short "
                "together, never by one leg."
            )


def _pairs_section(ctx: RunContext) -> None:
    res = ctx.result
    st.markdown("#### Contribution by pair")
    pa = pair_attribution(res)
    net = pa.loc[res.pair_names, "Net P&L"]
    winners = int((net > 0).sum())
    st.caption(f"**{winners} of {len(net)}** pairs made money after costs. "
               f"Best: **{net.idxmax()}** ({md_money(net.max())}). Worst: **{net.idxmin()}** ({md_money(net.min())}).")
    st.plotly_chart(charts.bar_chart(net, "Net P&L by pair (after trading and borrow costs)"),
                    width="stretch", config=PLOT_CFG)

    cum = res.pair_pnl()[res.pair_names].cumsum()
    st.plotly_chart(charts.pair_lines(cum, "Cumulative net P&L by pair", yfmt="$,.0f"),
                    width="stretch", config=PLOT_CFG)

    table = pa.copy()
    table.loc["Total"] = table.sum()
    st.dataframe(_money_table(table), width="stretch")
    st.caption(f"The **{OVERLAY}** row is the {ctx.config.benchmark} position used to hit your target beta. "
               "The rows add up exactly to the change in portfolio value.")


def _what_went_wrong(ctx: RunContext) -> None:
    res, cfg = ctx.result, ctx.config
    st.markdown("#### What went wrong? The worst drawdown, dissected", help=tip("drawdown"))
    win, contrib = drawdown_breakdown(res)
    if win.depth >= 0:
        st.success("This portfolio never had a drawdown. Check your inputs; that is not realistic.")
        return
    days = int(((res.nav.index > win.peak) & (res.nav.index <= win.trough)).sum())
    bench_move = float((1 + res.bench_returns.loc[(res.bench_returns.index > win.peak)
                                                  & (res.bench_returns.index <= win.trough)]).prod() - 1)
    c = st.columns(4)
    c[0].metric("Depth", f"{win.depth:.1%}", border=True)
    c[1].metric("Peak → trough", f"{win.peak:%b %Y} → {win.trough:%b %Y}", f"{days} trading days",
                delta_color="off", border=True)
    c[2].metric("Recovered", f"{win.recovery:%b %Y}" if win.recovery is not None else "Not yet", border=True)
    c[3].metric(f"{cfg.benchmark} over same period", f"{bench_move:+.1%}", border=True)

    fig = charts.equity_chart([("Portfolio", res.nav, charts.PORTFOLIO, "solid")],
                              "Equity curve with the worst drawdown shaded", height=340)
    fig.add_vrect(x0=win.peak, x1=win.trough, fillcolor="rgba(227,73,72,0.12)", line_width=0,
                  annotation_text="Worst drawdown", annotation_position="top left",
                  annotation_font=dict(color=charts.TEXT_2, size=11))
    st.plotly_chart(fig, width="stretch", config=PLOT_CFG)

    losers = contrib.drop("Cash interest", errors="ignore")
    worst_name, worst_val = losers.idxmin(), float(losers.min())
    total_loss = float(contrib.sum())
    left, right = st.columns([3, 2])
    with left:
        st.plotly_chart(charts.bar_chart(contrib, "P&L during the drawdown, by pair"),
                        width="stretch", config=PLOT_CFG)
    with right:
        share = worst_val / total_loss if total_loss < 0 and worst_val < 0 else float("nan")
        st.error(
            f"**Biggest detractor: {worst_name}**, which lost {md_money(abs(worst_val))} during this drawdown"
            + (f", about **{share:.0%}** of the total {md_money(abs(total_loss))} decline." if share == share else ".")
        )
        st.markdown(
            "**How a PM would use this:** check whether the damage came from *one* pair (an "
            "idiosyncratic blow-up: earnings miss, deal news, short squeeze) or from *many pairs at "
            "once* (a factor or crowding event, where everyone with similar positions sells at "
            "the same time). The first calls for position limits. The second calls for "
            "factor-risk monitoring and lower gross leverage."
        )
        if worst_name == OVERLAY:
            st.info("The beta overlay was the biggest loser here: the market exposure you chose, "
                    "not stock selection, drove this drawdown.")


def render(ctx: RunContext) -> None:
    _legs_section(ctx)
    st.divider()
    _pairs_section(ctx)
    st.divider()
    _what_went_wrong(ctx)
