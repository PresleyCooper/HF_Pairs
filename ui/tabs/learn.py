"""Learn tab: a short course on pairs trading and how backtests mislead."""

from __future__ import annotations

import streamlit as st

from ..glossary import GLOSSARY

PITFALLS: list[tuple[str, str, str]] = [
    (
        "Survivorship bias",
        "Yahoo Finance only has data for companies that still trade. Pairs that blew up, merged "
        "or went bankrupt are invisible, so any list of 'pairs that look good today' is "
        "pre-filtered for success. You picked KO/PEP *because* both are still around.",
        "Not fixable with free data. Be most skeptical of pairs chosen by looking at recent "
        "charts. Professional backtests use point-in-time universes that include dead companies.",
    ),
    (
        "Lookahead bias",
        "Using information you could not have had at the time: next quarter's earnings, a hedge "
        "ratio fitted on the whole period, or a pair you chose because you know how it ended.",
        "The engine sizes and hedges using only trailing data (tested in "
        "`tests/test_no_lookahead.py`). *Your* choice of pairs and the Diagnostics tab's "
        "full-sample statistics still carry hindsight.",
    ),
    (
        "Short squeezes and borrow availability",
        "The backtest assumes you can always borrow every short at a flat fee. In reality, "
        "lenders recall shares, fees spike to 20-100%+ on crowded names, and a squeeze (VW 2008, "
        "GameStop 2021) can force you to buy back at the worst moment.",
        "Raise the borrow fee in the sidebar to see how sensitive the book is. Large-cap "
        "pairs like the presets rarely face this. Small caps often do.",
    ),
    (
        "Crowding",
        "When many funds hold the same pairs, they all head for the exit together. In August "
        "2007 (the 'quant quake') market-neutral funds lost 10-30% in days, with the market "
        "barely moving, as one fund's forced selling hit everyone else's positions.",
        "Backtests on daily closes cannot see this. Watch the stress windows and the worst "
        "drawdown: losses spread across *all* pairs at once often signal a crowding event.",
    ),
    (
        "Past correlation can break",
        "Two stocks moved together because their businesses were similar. Businesses change: "
        "acquisitions, new product lines, regulation, a CEO change. A pair that was "
        "cointegrated for ten years can drift apart for the next ten.",
        "Use the Diagnostics tab's rolling correlation and z-score. Persistent z-scores beyond "
        "±3 mean the relationship is breaking, not that the trade is 'extra cheap'.",
    ),
    (
        "Costs and capacity",
        "A strategy that trades a lot looks great before costs. Market impact also grows with "
        "fund size: a \\$10m book and a \\$10bn book do not get the same prices.",
        "Try daily rebalancing with 10-20 bps costs and watch the Attribution tab's cost line.",
    ),
]

EXERCISES = [
    "**Beta vs alpha.** Load all seven presets. Note the Sharpe at β = 0, then slide to β = 1. How "
    "much of the β = 1 return came from the overlay? (Attribution tab, 'Net P&L by source'.)",
    "**Direction matters.** Flip KO / PEP. Why isn't the flipped result the exact mirror image? "
    "(Hint: costs, borrow, dividends and compounding.)",
    "**Hedges decay.** Set rebalancing to *Never*. Watch the ex-ante beta drift away from target on "
    "the Performance tab.",
    "**Dividends on the short.** Turn off 'Charge dividends to the short leg' and see how much a "
    "naive backtest would overstate returns.",
    "**Is it really a pair?** On the Diagnostics tab, which presets pass the cointegration test "
    "over 2015-today? Do they pass over 2005-2015?",
    "**Sizing.** Switch GM / F from dollar neutral to beta neutral. What happens to its residual beta "
    "and to its volatility?",
    "**Crisis test.** Which pair did the most damage in March 2020 on the Stress tab, and was the "
    "book still market neutral during the crash?",
]


def pitfalls_box() -> None:
    """Compact warning shown on the Overview tab."""
    st.warning(
        "**Before you trust this backtest.** It is optimistic by construction: it ignores "
        "**survivorship bias** (dead companies are missing), assumes you can **always borrow** every "
        "short at a flat fee with **no squeezes**, can't see **crowding**, and assumes **past "
        "relationships hold**. You also chose these pairs *knowing how they turned out* "
        "(**lookahead bias**). See the Learn tab for details.",
        icon="⚠️",
    )


def render() -> None:
    st.markdown("## How pairs trading works")
    st.markdown(
        """
**The idea.** Find two companies whose businesses are so similar that their stocks should move
together, such as Coca-Cola and PepsiCo. Buy the one you think will do better and short the other.
If the whole market falls 20%, both legs fall and the loss on your long is roughly offset by
the gain on your short. What's left is the *relative* performance: did KO beat PEP? That relative
bet is the whole trade.

**Building the book.** A long/short equity fund runs many pairs at once:

1. **Size each pair.** Each pair gets a share of *gross exposure* (long \\$ + short \\$). With
   \\$100m of capital at 2x gross, a 10% pair gets \\$20m: \\$10m long and \\$10m short if
   *dollar neutral*.
2. **Balance the legs.** Equal dollars isn't always equal risk. If the long has a beta of 1.3 and
   the short 0.8, a dollar-neutral pair is still net long the market. *Beta-neutral* sizing
   shorts more of the low-beta leg so the pair's beta is zero. *Volatility matching* equalizes
   each leg's risk.
3. **Hedge what's left.** Estimated betas never cancel perfectly, so funds add an index hedge
   (here, the benchmark ETF overlay) to bring the whole book to a *target beta*.
4. **Pay to play.** Shorting costs a borrow fee. Short-sale proceeds earn interest. Every trade
   costs commission and spread.
5. **Rebalance.** Winners grow and losers shrink, so the book drifts. Rebalancing resets the
   sizes and the hedge, at the cost of more trading.
        """
    )

    st.markdown("## Why funds run it")
    st.markdown(
        """
- **Low correlation to the market.** Investors already own plenty of beta through index funds.
  They pay hedge fund fees for returns that *don't* come from the market (alpha).
- **Diversification.** A market-neutral book can make money in a bear market, which is when a
  pension fund most needs it.
- **Separating skill from luck.** Hedging out beta shows whether the analyst can actually pick
  the better company, and that can be measured and paid for.
- **Leverage-friendly.** Because the market risk is hedged, funds run 2-6x gross to turn small
  relative edges into meaningful returns. That is also why the blow-ups are big.
        """
    )

    st.markdown("## How it fails")
    st.markdown(
        """
- **The relationship breaks.** One company changes: a big acquisition, a new business line, a
  scandal. The 'pair' becomes two unrelated stocks and the spread never comes back.
- **The short squeezes.** A heavily shorted stock jumps on news or a buying frenzy. Shorts are
  forced to buy back, which drives the price higher still. Losses on a short have no ceiling.
- **Everyone has the same trade.** Crowded pairs unwind together when funds deleverage at the
  same moment (August 2007, March 2020).
- **Factor exposure in disguise.** Long cheap stocks / short expensive ones looks like 20 different
  pairs but is really one bet on *value vs growth*. It loses on all 20 at once when that factor
  turns (see the Stress tab's value rotation).
- **Leverage + time.** Even a correct trade can lose if the spread widens further before it
  converges and your lenders or investors pull capital first.
        """
    )

    st.markdown("## ⚠️ Backtest pitfalls")
    st.caption("Every backtest is a model, and these are the main ways this one can mislead you.")
    for title, problem, handling in PITFALLS:
        with st.container(border=True):
            st.markdown(f"**{title}**")
            st.markdown(problem)
            st.markdown(f"*In this app:* {handling}")

    st.markdown("## Try these")
    for i, ex in enumerate(EXERCISES, start=1):
        st.markdown(f"{i}. {ex}")

    st.markdown("## Glossary")
    labels = {
        "beta": "Beta", "target_beta": "Target beta", "alpha": "Alpha", "gross_net": "Gross vs net exposure",
        "gross_leverage": "Gross leverage", "dollar_vs_beta": "Dollar neutral vs beta neutral vs vol matched",
        "overlay": "Beta overlay", "borrow": "Borrow cost", "cash_rate": "Interest on cash & short proceeds",
        "tc": "Transaction costs", "short_dividends": "Dividends on the short leg", "rebalance": "Rebalancing",
        "beta_window": "Beta estimation window", "benchmark": "Benchmark", "sharpe": "Sharpe ratio",
        "sortino": "Sortino ratio", "drawdown": "Drawdown", "calmar": "Calmar ratio",
        "hit_rate": "Hit rate", "correlation": "Correlation",
    }
    cols = st.columns(2)
    for i, (key, label) in enumerate(labels.items()):
        with cols[i % 2].expander(label):
            st.markdown(GLOSSARY[key])
