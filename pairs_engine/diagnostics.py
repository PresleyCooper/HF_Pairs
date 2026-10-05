"""Statistical diagnostics for a single pair.

These are the questions a PM asks before putting a pair on:

* Do the two stocks actually move together (correlation)?
* Is there a stable long-run relationship between their prices
  (cointegration), or do they just happen to trend the same way?
* When the spread between them widens, how fast does it snap back
  (half-life)?
* Where is the spread today relative to its recent range (z-score)?

Two flavors of number appear here, and the difference matters:

* *Trailing* statistics (rolling mean/std bands, z-score, rolling
  correlation) only use past data, like the backtest.
* *Full-sample* statistics (OLS hedge ratio, Engle-Granger test,
  half-life) are fitted on the whole window. They describe the period
  after the fact and would be lookahead if you traded on them.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd

from .beta import rolling_corr
from .data import PriceData


@dataclass
class PairDiagnostics:
    long: str
    short: str
    log_ratio: pd.Series  # ln(long / short)
    ratio_mean: pd.Series  # trailing mean of the log ratio
    ratio_std: pd.Series  # trailing std of the log ratio
    zscore: pd.Series  # (log_ratio - trailing mean) / trailing std
    rolling_corr: pd.Series  # trailing correlation of daily returns
    return_corr: float  # full-sample correlation of daily returns
    hedge_ratio: float  # OLS slope of ln(long) on ln(short)
    intercept: float
    r_squared: float
    spread: pd.Series  # ln(long) - hedge_ratio * ln(short) - intercept
    coint_pvalue: float  # Engle-Granger test p-value
    half_life: float  # trading days; inf if the spread does not mean-revert
    n_obs: int


def ols_hedge_ratio(y: pd.Series, x: pd.Series) -> tuple[float, float, float]:
    """Regress y on x with a constant. Returns (slope, intercept, R²)."""
    xv, yv = x.to_numpy(float), y.to_numpy(float)
    slope, intercept = np.polyfit(xv, yv, 1)
    resid = yv - (slope * xv + intercept)
    ss_tot = ((yv - yv.mean()) ** 2).sum()
    r2 = 1 - (resid ** 2).sum() / ss_tot if ss_tot > 0 else float("nan")
    return float(slope), float(intercept), float(r2)


def half_life(spread: pd.Series) -> float:
    """Mean-reversion half-life in trading days, from an AR(1) fit.

    Regress the daily change in the spread on yesterday's level:
    Δs_t = c + λ·s_{t-1} + ε. If λ < 0 the spread is pulled back toward its
    mean, and the half-life is -ln(2)/λ: how long a gap takes to close
    halfway. If λ ≥ 0 there is no pull back, so the half-life is infinite.
    """
    s = spread.dropna()
    if len(s) < 10:
        return float("nan")
    lag = s.shift(1).iloc[1:]
    delta = s.diff().iloc[1:]
    lam, _ = np.polyfit(lag.to_numpy(float), delta.to_numpy(float), 1)
    return float(-math.log(2) / lam) if lam < 0 else float("inf")


def engle_granger_pvalue(y: pd.Series, x: pd.Series) -> float:
    """p-value of the Engle-Granger cointegration test (statsmodels)."""
    from statsmodels.tsa.stattools import coint

    _, pvalue, _ = coint(y.to_numpy(float), x.to_numpy(float), trend="c", autolag="aic")
    return float(pvalue)


def diagnose_pair(
    data: PriceData,
    long: str,
    short: str,
    start: pd.Timestamp | None = None,
    end: pd.Timestamp | None = None,
    window: int = 60,
) -> PairDiagnostics:
    """Compute every diagnostic for one pair on total-return (adjusted) prices."""
    px = data.total[[long, short]]
    if start is not None:
        px = px.loc[pd.Timestamp(start):]
    if end is not None:
        px = px.loc[:pd.Timestamp(end)]
    px = px.dropna()
    if len(px) < max(window + 2, 30):
        raise ValueError(f"Not enough overlapping history for {long}/{short} ({len(px)} days).")

    logs = np.log(px)
    log_ratio = (logs[long] - logs[short]).rename("Log ratio")
    mean = log_ratio.rolling(window, min_periods=window).mean()
    std = log_ratio.rolling(window, min_periods=window).std()
    z = ((log_ratio - mean) / std).rename("Z-score")

    rets = px.pct_change(fill_method=None)
    rc = rolling_corr(rets[long], rets[short], window).rename("Rolling correlation")

    slope, intercept, r2 = ols_hedge_ratio(logs[long], logs[short])
    spread = (logs[long] - slope * logs[short] - intercept).rename("OLS spread")

    return PairDiagnostics(
        long=long,
        short=short,
        log_ratio=log_ratio,
        ratio_mean=mean,
        ratio_std=std,
        zscore=z,
        rolling_corr=rc,
        return_corr=float(rets[long].corr(rets[short])),
        hedge_ratio=slope,
        intercept=intercept,
        r_squared=r2,
        spread=spread,
        coint_pvalue=engle_granger_pvalue(logs[long], logs[short]),
        half_life=half_life(spread),
        n_obs=len(px),
    )


def coint_verdict(p: float) -> str:
    if not math.isfinite(p):
        return "n/a"
    if p < 0.05:
        return "Cointegrated (5% level)"
    if p < 0.10:
        return "Weak evidence (10% level)"
    return "Not cointegrated"


def half_life_verdict(hl: float) -> str:
    if not math.isfinite(hl):
        return "No mean reversion"
    if hl <= 20:
        return "Fast (≤ 1 month)"
    if hl <= 120:
        return "Moderate (1-6 months)"
    return "Slow (> 6 months)"
