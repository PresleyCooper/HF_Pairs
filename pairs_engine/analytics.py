"""Performance statistics, drawdowns and P&L attribution.

Return-based statistics use daily returns. Ratios that need a risk-free rate
(Sharpe, Sortino, alpha) use the backtest's cash rate, because that is what
an investor could have earned doing nothing.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .backtest import OVERLAY, BacktestResult
from .beta import rolling_beta, rolling_corr
from .data import TRADING_DAYS_PER_YEAR

ANN = TRADING_DAYS_PER_YEAR

# Display order and formatting hints for the summary table.
STAT_FORMATS: dict[str, str] = {
    "Total return": "pct",
    "CAGR": "pct",
    "Annualized volatility": "pct",
    "Sharpe ratio": "num",
    "Sortino ratio": "num",
    "Max drawdown": "pct",
    "Calmar ratio": "num",
    "Realized beta": "num",
    "Alpha (annualized)": "pct",
    "Correlation to benchmark": "num",
    "Hit rate (daily)": "pct",
    "Average winning day": "pct",
    "Average losing day": "pct",
    "Win/loss ratio": "num",
}


def drawdown(nav: pd.Series) -> pd.Series:
    """Percent below the running peak, as a negative number (0 at new highs)."""
    return nav / nav.cummax() - 1.0


@dataclass(frozen=True)
class DrawdownWindow:
    peak: pd.Timestamp
    trough: pd.Timestamp
    recovery: pd.Timestamp | None  # None if the NAV never regained the peak
    depth: float  # negative, e.g. -0.18 for an 18% drawdown


def worst_drawdown(nav: pd.Series) -> DrawdownWindow:
    """Locate the peak, trough and recovery of the deepest drawdown."""
    dd = drawdown(nav)
    trough = dd.idxmin()
    peak = nav.loc[:trough].idxmax()
    after = nav.loc[trough:]
    recovered = after[after >= nav.loc[peak]]
    recovery = recovered.index[0] if len(recovered) else None
    return DrawdownWindow(peak, trough, recovery, float(dd.loc[trough]))


def _ols_alpha_beta(y: np.ndarray, x: np.ndarray) -> tuple[float, float]:
    if len(y) < 3 or np.var(x) == 0:
        return float("nan"), float("nan")
    beta = np.cov(y, x, ddof=1)[0, 1] / np.var(x, ddof=1)
    alpha = y.mean() - beta * x.mean()
    return float(alpha), float(beta)


def summary_stats(
    returns: pd.Series,
    bench_returns: pd.Series,
    rf_annual: float = 0.0,
) -> dict[str, float]:
    """The standard hedge fund tear-sheet numbers for one return stream."""
    r = returns.dropna()
    b = bench_returns.reindex(r.index).fillna(0.0)
    n = len(r)
    if n < 2:
        return {k: float("nan") for k in STAT_FORMATS}

    rf_daily = rf_annual / ANN
    nav = (1.0 + r).cumprod()
    total = float(nav.iloc[-1] - 1.0)
    years = max((r.index[-1] - r.index[0]).days / 365.25, 1 / ANN)
    cagr = float(nav.iloc[-1] ** (1 / years) - 1.0) if nav.iloc[-1] > 0 else -1.0
    vol = float(r.std(ddof=1) * np.sqrt(ANN))

    excess = r - rf_daily
    sharpe = float(excess.mean() / r.std(ddof=1) * np.sqrt(ANN)) if r.std() > 0 else float("nan")
    downside = np.sqrt(np.mean(np.minimum(excess, 0.0) ** 2))
    sortino = float(excess.mean() / downside * np.sqrt(ANN)) if downside > 0 else float("nan")
    mdd = float(drawdown(nav).min())
    calmar = cagr / abs(mdd) if mdd < 0 else float("nan")

    # CAPM regression on excess returns: (r - rf) = alpha + beta * (b - rf)
    alpha_d, beta = _ols_alpha_beta(excess.to_numpy(), (b - rf_daily).to_numpy())
    corr = float(r.corr(b)) if b.std() > 0 else float("nan")

    wins, losses = r[r > 0], r[r < 0]
    traded_days = len(wins) + len(losses)
    hit = len(wins) / traded_days if traded_days else float("nan")
    avg_win = float(wins.mean()) if len(wins) else float("nan")
    avg_loss = float(losses.mean()) if len(losses) else float("nan")
    wl = abs(avg_win / avg_loss) if len(wins) and len(losses) else float("nan")

    return {
        "Total return": total,
        "CAGR": cagr,
        "Annualized volatility": vol,
        "Sharpe ratio": sharpe,
        "Sortino ratio": sortino,
        "Max drawdown": mdd,
        "Calmar ratio": calmar,
        "Realized beta": beta,
        "Alpha (annualized)": alpha_d * ANN,
        "Correlation to benchmark": corr,
        "Hit rate (daily)": hit,
        "Average winning day": avg_win,
        "Average losing day": avg_loss,
        "Win/loss ratio": wl,
    }


def result_stats(result: BacktestResult) -> dict[str, float]:
    return summary_stats(result.returns, result.bench_returns, result.config.cash_rate)


def realized_rolling_beta(result: BacktestResult, window: int | None = None) -> pd.Series:
    """Ex-post beta of the portfolio's actual daily returns to the benchmark."""
    window = window or result.config.beta_window
    df = rolling_beta(result.returns.to_frame("Portfolio"), result.bench_returns, window)
    return df["Portfolio"].rename("Realized beta")


def realized_rolling_corr(result: BacktestResult, window: int | None = None) -> pd.Series:
    window = window or result.config.beta_window
    return rolling_corr(result.returns, result.bench_returns, window).rename("Rolling correlation")


# ----------------------------------------------------------------------------
# Attribution
# ----------------------------------------------------------------------------

def pair_attribution(result: BacktestResult) -> pd.DataFrame:
    """Dollar P&L by pair (and overlay), split into its components.

    The rows plus the "Cash interest" row add up exactly to the change in
    NAV.
    """
    cap = result.config.initial_capital
    meta = result.slots.set_index("slot")
    rows = []
    for name in result.pair_names + [OVERLAY]:
        slots = meta.index[meta["pair"] == name]
        legs = meta.loc[slots, "leg"]
        long_s = slots[legs == "long"]
        short_s = slots[legs == "short"]
        over_s = slots[legs == "overlay"]
        rows.append({
            "Pair": name,
            "Long leg P&L": float(result.market_pnl[long_s].to_numpy().sum()),
            "Short leg P&L": float(result.market_pnl[short_s].to_numpy().sum()),
            "Overlay P&L": float(result.market_pnl[over_s].to_numpy().sum()),
            "Trading costs": -float(result.trading_costs[slots].to_numpy().sum()),
            "Borrow costs": -float(result.borrow_costs[slots].to_numpy().sum()),
        })
    rows.append({"Pair": "Cash interest", "Long leg P&L": 0.0, "Short leg P&L": 0.0,
                 "Overlay P&L": 0.0, "Trading costs": 0.0, "Borrow costs": 0.0,
                 "Interest": float(result.interest.sum())})
    df = pd.DataFrame(rows).set_index("Pair").fillna(0.0)
    df["Net P&L"] = df.sum(axis=1)
    df["Contribution (% of capital)"] = df["Net P&L"] / cap
    return df


def leg_attribution(result: BacktestResult) -> pd.Series:
    """Where the money came from, in dollars: longs, shorts, overlay, costs, cash."""
    legs = result.slots.set_index("slot")["leg"]
    by_leg = result.market_pnl.sum().groupby(legs).sum()
    return pd.Series({
        "Long legs": float(by_leg.get("long", 0.0)),
        "Short legs": float(by_leg.get("short", 0.0)),
        "Beta overlay": float(by_leg.get("overlay", 0.0)),
        "Trading costs": -float(result.trading_costs.to_numpy().sum()),
        "Borrow costs": -float(result.borrow_costs.to_numpy().sum()),
        "Cash interest": float(result.interest.sum()),
    })


def pair_returns(result: BacktestResult) -> pd.DataFrame:
    """Daily return of each pair on the capital allocated to it.

    Allocated capital is the pair's gross notional divided by gross leverage,
    i.e. the slice of NAV backing that pair. Interest is excluded, so this
    is the pair's return in excess of cash, roughly.
    """
    pnl = result.pair_pnl()[result.pair_names]
    meta = result.slots.set_index("slot")
    out = {}
    for name in result.pair_names:
        slots = meta.index[meta["pair"] == name]
        gross_prev = result.positions[slots].abs().sum(axis=1).shift(1)
        alloc = gross_prev / result.config.gross_leverage
        out[name] = (pnl[name] / alloc.replace(0.0, np.nan)).fillna(0.0)
    return pd.DataFrame(out, index=result.nav.index)


def drawdown_breakdown(result: BacktestResult) -> tuple[DrawdownWindow, pd.Series]:
    """Net P&L of each pair and the overlay during the worst drawdown.

    Sorted worst first, so the top row is the pair that hurt the most.
    """
    win = worst_drawdown(result.nav)
    pnl = result.pair_pnl()
    # P&L that occurred after the peak close through the trough close.
    mask = (pnl.index > win.peak) & (pnl.index <= win.trough)
    contrib = pnl.loc[mask].sum()
    contrib["Cash interest"] = float(result.interest.loc[mask].sum())
    return win, contrib.sort_values()


def daily_report(result: BacktestResult) -> pd.DataFrame:
    """One row per trading day: NAV, returns, betas, exposures and P&L by pair.

    This is the table behind the app's CSV download.
    """
    nav = result.nav
    legs = result.slots.set_index("slot")["leg"]
    pos = result.positions
    pnl = result.pair_pnl().add_suffix(" net P&L")
    df = pd.DataFrame({
        "NAV": nav,
        "Portfolio return": result.returns,
        f"{result.config.benchmark} return": result.bench_returns,
        "Ex-ante beta": result.total_beta,
        "Pair book beta": result.book_beta,
        "Realized rolling beta": realized_rolling_beta(result),
        "Long exposure ($)": pos.loc[:, (legs == "long").to_numpy()].sum(axis=1),
        "Short exposure ($)": pos.loc[:, (legs == "short").to_numpy()].sum(axis=1),
        "Overlay exposure ($)": pos.loc[:, (legs == "overlay").to_numpy()].sum(axis=1),
        "Trading costs": result.trading_costs.sum(axis=1),
        "Borrow costs": result.borrow_costs.sum(axis=1),
        "Cash interest": result.interest,
    })
    return pd.concat([df, pnl], axis=1).rename_axis("Date")
