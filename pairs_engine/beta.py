"""Rolling, point-in-time risk estimates.

Every function here uses a *trailing* window: the value stamped on day ``t``
uses returns from ``t - window + 1`` through ``t`` and nothing later. That is
what makes the backtest free of lookahead. A decision made at the close of
``t`` can only use what was known at that close.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .data import TRADING_DAYS_PER_YEAR


def rolling_beta(returns: pd.DataFrame, bench: pd.Series, window: int) -> pd.DataFrame:
    """OLS beta of each column against ``bench`` over a trailing window.

    beta = cov(asset, bench) / var(bench). This is exactly the slope of a
    one-factor regression, computed in closed form so it's fast.
    """
    var = bench.rolling(window, min_periods=window).var()
    out = {}
    for col in returns.columns:
        cov = returns[col].rolling(window, min_periods=window).cov(bench)
        out[col] = cov / var
    return pd.DataFrame(out, index=returns.index)


def rolling_vol(returns: pd.DataFrame, window: int) -> pd.DataFrame:
    """Annualised trailing standard deviation of daily returns."""
    return returns.rolling(window, min_periods=window).std() * np.sqrt(TRADING_DAYS_PER_YEAR)


def rolling_corr(a: pd.Series, b: pd.Series, window: int) -> pd.Series:
    """Trailing correlation between two return series."""
    return a.rolling(window, min_periods=window).corr(b)
