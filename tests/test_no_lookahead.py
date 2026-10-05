"""The engine must never use information from the future.

Strategy: run a backtest, then change every price *after* a cut-off date and
run it again. Nothing stamped on or before the day before the cut-off
(positions, NAV, betas) may change. If any of it did, the engine would be
peeking at future data.
"""

import numpy as np
import pandas as pd

from pairs_engine import PairSpec, PriceData, RebalanceFreq, SizingMethod, run_backtest
from pairs_engine.beta import rolling_beta, rolling_vol

from .conftest import config_for, make_market

PAIRS = [
    PairSpec("AAA", "BBB", sizing=SizingMethod.BETA_NEUTRAL),
    PairSpec("CCC", "DDD", sizing=SizingMethod.VOL_MATCHED),
    PairSpec("DDD", "AAA"),
]


def _corrupt_after(data: PriceData, cut: int, seed: int = 99) -> PriceData:
    rng = np.random.default_rng(seed)
    shock = pd.DataFrame(
        np.exp(np.cumsum(rng.normal(0, 0.05, data.total.shape), axis=0)),
        index=data.index, columns=data.tickers,
    )
    shock.iloc[:cut] = 1.0
    return PriceData(price=data.price * shock, total=data.total * shock)


def _assert_same_until(a, b, last):
    pd.testing.assert_series_equal(a.nav.loc[:last], b.nav.loc[:last])
    pd.testing.assert_frame_equal(a.positions.loc[:last], b.positions.loc[:last])
    pd.testing.assert_series_equal(a.total_beta.loc[:last], b.total_beta.loc[:last])
    pd.testing.assert_series_equal(a.book_beta.loc[:last], b.book_beta.loc[:last])


def test_future_prices_do_not_change_past_decisions():
    data = make_market(idio=0.01, seed=7)
    cut = 350
    cfg = config_for(data, rebalance=RebalanceFreq.DAILY, target_beta=0.5)
    base = run_backtest(PAIRS, cfg, data)
    alt = run_backtest(PAIRS, cfg, _corrupt_after(data, cut))
    last = data.index[cut - 1]
    _assert_same_until(base, alt, last)
    # Sanity: the corruption really did change the future.
    assert not np.isclose(base.nav.iloc[-1], alt.nav.iloc[-1])


def test_truncated_history_gives_identical_past():
    data = make_market(idio=0.01, seed=11)
    cfg = config_for(data, rebalance=RebalanceFreq.WEEKLY, target_beta=-0.25)
    full = run_backtest(PAIRS, cfg, data)
    cut = 400
    short_data = PriceData(price=data.price.iloc[:cut], total=data.total.iloc[:cut])
    short_cfg = config_for(short_data, rebalance=RebalanceFreq.WEEKLY, target_beta=-0.25)
    short = run_backtest(PAIRS, short_cfg, short_data)
    _assert_same_until(full, short, short_data.index[-1])


def test_rolling_estimates_are_trailing():
    data = make_market(idio=0.01, seed=5)
    rets = data.total_returns()
    cut = 300
    shocked = rets.copy()
    shocked.iloc[cut:] *= 10.0
    b1 = rolling_beta(rets[["AAA"]], rets["SPY"], 60)
    b2 = rolling_beta(shocked[["AAA"]], shocked["SPY"], 60)
    v1 = rolling_vol(rets[["AAA"]], 60)
    v2 = rolling_vol(shocked[["AAA"]], 60)
    pd.testing.assert_frame_equal(b1.iloc[:cut], b2.iloc[:cut])
    pd.testing.assert_frame_equal(v1.iloc[:cut], v2.iloc[:cut])
    # The first window value needs a full window of returns.
    assert b1["AAA"].first_valid_index() == rets.index[60]
