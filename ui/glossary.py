"""Plain-English explanations used for tooltips and info expanders.

Keeping every explanation in one place means the wording stays consistent
across the app, and a student org officer can edit the teaching content
without touching any layout code.
"""

from __future__ import annotations

GLOSSARY: dict[str, str] = {
    "beta": (
        "**Beta** measures how much a position moves with the market. A beta of 1.0 means "
        "that when the benchmark rises 1%, the position tends to rise 1%. A beta of 0 means "
        "no systematic link to the market. Beta is estimated by regressing daily returns on "
        "the benchmark's returns."
    ),
    "target_beta": (
        "The net market exposure you want the whole portfolio to carry. 0 means market "
        "neutral. 0.3 means a 'low net' fund that keeps some upside to the market. The app "
        "hits this by adding a long or short position in the benchmark ETF (the overlay)."
    ),
    "alpha": (
        "**Alpha** is the return left over after accounting for market exposure: the part "
        "of performance that beta does not explain. It is what investors pay hedge fund "
        "fees for. Here it is the intercept of a regression of excess returns on the "
        "benchmark's excess returns, annualized."
    ),
    "gross_net": (
        "**Gross exposure** = long \\$ + short \\$ (how much capital is at work). **Net "
        "exposure** = long \\$ − short \\$ (directional bet). A fund with \\$100 of capital, \\$100 "
        "long and \\$100 short is 200% gross and 0% net. Gross drives risk and costs. Net "
        "drives market sensitivity, but only if both legs have similar beta."
    ),
    "gross_leverage": (
        "Gross exposure of the pair book as a multiple of capital. 2.0x means each \\$1 of "
        "capital supports \\$2 of positions, e.g. \\$1 long + \\$1 short. The beta overlay is "
        "extra and not counted here."
    ),
    "dollar_vs_beta": (
        "**Dollar neutral**: equal dollars long and short. Simple, but if the long has a "
        "beta of 1.3 and the short 0.8, you are still net long the market. "
        "**Beta neutral**: the short leg is sized so the pair has zero beta (long × β_long = "
        "short × β_short). **Volatility matched**: each leg carries the same risk (long × "
        "σ_long = short × σ_short)."
    ),
    "overlay": (
        "The **beta overlay** is a position in the benchmark ETF (e.g. SPY) that tops the "
        "portfolio up or down to the target beta. If the pair book has a beta of 0.2 and the "
        "target is 0, the overlay shorts 0.2 × NAV of SPY. Many funds do this with index "
        "futures instead."
    ),
    "borrow": (
        "To short a stock you borrow it from a lender and pay an annual **borrow fee** on its "
        "value. Large, liquid stocks are 'general collateral' at roughly 0.25-0.5% a year. "
        "Crowded or hard-to-borrow names can cost 10-100%+, and the lender can recall the "
        "shares at any time."
    ),
    "cash_rate": (
        "Interest earned on idle cash *and* on the proceeds from short sales, which stay at "
        "the broker as collateral. If leverage pushes cash below zero, the same rate is "
        "charged. A simplification: real funds pay a spread."
    ),
    "tc": (
        "Cost per dollar traded, in basis points (1 bp = 0.01%). It covers commission, half "
        "the bid/ask spread and market impact. 2-10 bp is typical for large caps. It is "
        "charged on every rebalance trade, so frequent rebalancing costs more."
    ),
    "short_dividends": (
        "When you are short a stock that pays a dividend, **you** pay that dividend to the "
        "lender. Leave this on for an accurate backtest. Turn it off to see how much "
        "ignoring it flatters a short book."
    ),
    "rebalance": (
        "How often positions are reset to target sizes and the beta hedge is refreshed. "
        "**Never** means buy on day one and let winners and losers drift, so the hedge decays "
        "over time."
    ),
    "beta_window": (
        "Number of trading days used to estimate each stock's beta and volatility. Shorter "
        "reacts faster but is noisier. 60 days is about three months; 252 is about a year."
    ),
    "benchmark": (
        "The market index the portfolio's beta is measured against, and the ETF used for "
        "the overlay. SPY = S&P 500, QQQ = Nasdaq-100, IWM = Russell 2000 small caps, "
        "DIA = Dow 30."
    ),
    "sharpe": (
        "**Sharpe ratio** = (return − cash rate) ÷ volatility, annualized. Return per unit of "
        "total risk. Above 1.0 is good for a hedge fund, and above 2.0 over long periods is rare."
    ),
    "sortino": (
        "Like Sharpe, but it divides by *downside* volatility only, so funds are not "
        "penalized for big up days."
    ),
    "drawdown": (
        "**Drawdown** is the percent decline from the previous peak. **Max drawdown** is the "
        "worst one. Investors often redeem after large drawdowns, so funds manage this "
        "number closely."
    ),
    "calmar": "**Calmar ratio** = CAGR ÷ |max drawdown|: return per unit of worst-case pain.",
    "hit_rate": (
        "Share of days with a positive return. Pairs books often win only slightly more than "
        "half the time. What matters is how big the wins are against the losses."
    ),
    "correlation": (
        "How closely daily returns move together, from −1 to +1. A market-neutral fund should "
        "show a correlation near 0 to the benchmark."
    ),
}


def tip(key: str) -> str:
    """Tooltip text for ``key`` (Streamlit ``help=`` renders markdown)."""
    return GLOSSARY[key]


# Which glossary entry explains each row of the stats table.
STAT_TIPS: dict[str, str] = {
    "Sharpe ratio": "sharpe",
    "Sortino ratio": "sortino",
    "Max drawdown": "drawdown",
    "Calmar ratio": "calmar",
    "Realized beta": "beta",
    "Alpha (annualized)": "alpha",
    "Correlation to benchmark": "correlation",
    "Hit rate (daily)": "hit_rate",
}
