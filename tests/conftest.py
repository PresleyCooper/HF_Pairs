"""Synthetic market fixtures. No test touches the network."""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import pytest

from pairs_engine import BacktestConfig, PriceData

DEFAULT_BETAS = {"AAA": 1.2, "BBB": 0.8, "CCC": 1.0, "DDD": 0.5}


def make_market(
    n: int = 600,
    betas: dict[str, float] | None = None,
    idio: float = 0.0,
    seed: int = 0,
    start: str = "2020-01-01",
) -> PriceData:
    """One-factor market: each stock's return = beta * SPY return + noise.

    With ``idio=0`` the stocks are exact linear functions of the market, so
    rolling betas equal the true betas to floating-point precision.
    """
    betas = betas or DEFAULT_BETAS
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range(start, periods=n)
    rm = rng.normal(0.0004, 0.01, n)
    rm[0] = 0.0
    cols = {"SPY": 100 * np.cumprod(1 + rm)}
    for tk, b in betas.items():
        eps = rng.normal(0.0, idio, n) if idio else 0.0
        r = b * rm + eps
        r = np.where(np.arange(n) == 0, 0.0, r)
        cols[tk] = 50 * np.cumprod(1 + r)
    return PriceData.from_total(pd.DataFrame(cols, index=dates))


def config_for(data: PriceData, warmup: int = 100, **overrides) -> BacktestConfig:
    """Config whose start leaves ``warmup`` days for the beta window."""
    idx = data.index
    kwargs = dict(
        start=idx[warmup].date(),
        end=idx[-1].date(),
        beta_window=60,
        initial_capital=1_000_000.0,
        gross_leverage=2.0,
    )
    kwargs.update(overrides)
    return BacktestConfig(**kwargs)


@pytest.fixture
def market() -> PriceData:
    return make_market()


@pytest.fixture
def noisy_market() -> PriceData:
    return make_market(idio=0.01, seed=1)


@pytest.fixture
def epoch() -> date:
    return date(2020, 1, 1)
