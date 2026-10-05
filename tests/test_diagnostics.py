import math

import numpy as np
import pandas as pd
import pytest

from pairs_engine import PriceData
from pairs_engine.diagnostics import diagnose_pair, half_life, ols_hedge_ratio


def cointegrated_prices(n=1500, beta=1.3, phi=0.9, seed=0) -> PriceData:
    """ln(A) = beta * ln(B) + s, where s is a stationary AR(1) with coefficient phi."""
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2015-01-01", periods=n)
    log_b = np.log(50) + np.cumsum(rng.normal(0, 0.01, n))
    s = np.zeros(n)
    for t in range(1, n):
        s[t] = phi * s[t - 1] + rng.normal(0, 0.01)
    log_a = 0.2 + beta * log_b + s
    walk = np.log(30) + np.cumsum(rng.normal(0, 0.01, n))  # unrelated random walk
    df = pd.DataFrame({"A": np.exp(log_a), "B": np.exp(log_b), "C": np.exp(walk)}, index=idx)
    return PriceData.from_total(df)


def test_cointegrated_pair_detected():
    d = diagnose_pair(cointegrated_prices(), "A", "B")
    assert d.coint_pvalue < 0.05
    assert d.hedge_ratio == pytest.approx(1.3, abs=0.05)
    # AR(1) with phi=0.9 -> lambda = -0.1 -> half-life = ln2 / 0.1 ≈ 6.9 days
    assert d.half_life == pytest.approx(math.log(2) / 0.1, rel=0.25)


def test_unrelated_random_walks_not_cointegrated():
    d = diagnose_pair(cointegrated_prices(seed=4), "A", "C")
    assert d.coint_pvalue > 0.05


def test_half_life_infinite_for_trending_spread():
    s = pd.Series(np.linspace(0, 1, 200) ** 2)
    assert half_life(s) == float("inf")


def test_ols_hedge_ratio_exact():
    x = pd.Series(np.arange(1.0, 50.0))
    slope, intercept, r2 = ols_hedge_ratio(2.5 * x + 1.0, x)
    assert (slope, intercept) == (pytest.approx(2.5), pytest.approx(1.0))
    assert r2 == pytest.approx(1.0)


def test_zscore_is_trailing():
    data = cointegrated_prices()
    full = diagnose_pair(data, "A", "B", window=60)
    cut = 800
    truncated = PriceData.from_total(data.total.iloc[:cut])
    part = diagnose_pair(truncated, "A", "B", window=60)
    pd.testing.assert_series_equal(full.zscore.iloc[:cut], part.zscore)
    pd.testing.assert_series_equal(full.rolling_corr.iloc[:cut], part.rolling_corr)


def test_short_history_rejected():
    data = cointegrated_prices(n=40)
    with pytest.raises(ValueError):
        diagnose_pair(data, "A", "B", window=60)
