import math

import numpy as np
import pytest

from pairs_engine import PairSpec, RebalanceFreq, SizingMethod, run_backtest
from pairs_engine.sizing import size_pair

from .conftest import config_for, make_market

G = 1_000_000.0


def test_dollar_neutral_splits_evenly():
    s = size_pair(SizingMethod.DOLLAR_NEUTRAL, G, beta_long=1.5, beta_short=0.5)
    assert s.long == s.short == G / 2


def test_beta_neutral_zero_net_beta_and_keeps_gross():
    s = size_pair(SizingMethod.BETA_NEUTRAL, G, beta_long=1.2, beta_short=0.8)
    assert s.long * 1.2 == pytest.approx(s.short * 0.8)
    assert s.long + s.short == pytest.approx(G)
    # Higher-beta long leg gets fewer dollars.
    assert s.long < s.short


def test_vol_matched_equal_risk_and_keeps_gross():
    s = size_pair(SizingMethod.VOL_MATCHED, G, vol_long=0.30, vol_short=0.15)
    assert s.long * 0.30 == pytest.approx(s.short * 0.15)
    assert s.long + s.short == pytest.approx(G)


def test_floor_caps_extreme_ratios():
    s = size_pair(SizingMethod.BETA_NEUTRAL, G, beta_long=1.0, beta_short=-0.3, floor=0.1)
    assert s.floored
    # short beta treated as 0.1, so long:short = 0.1:1.0
    assert s.long / s.short == pytest.approx(0.1)


def test_missing_estimates_fall_back_to_dollar_neutral():
    s = size_pair(SizingMethod.BETA_NEUTRAL, G, beta_long=math.nan, beta_short=1.0)
    assert s.fallback
    assert s.long == s.short == G / 2


def test_pair_spec_flip_and_normalisation():
    p = PairSpec(" ko", "pep ", weight=2.0)
    assert (p.long, p.short) == ("KO", "PEP")
    f = p.flipped()
    assert (f.long, f.short, f.weight) == ("PEP", "KO", 2.0)
    with pytest.raises(ValueError):
        PairSpec("KO", "ko")


def test_beta_neutral_pair_has_zero_book_beta_in_backtest():
    data = make_market()  # exact one-factor market, betas known
    pairs = [PairSpec("AAA", "BBB", sizing=SizingMethod.BETA_NEUTRAL)]
    cfg = config_for(data, rebalance=RebalanceFreq.DAILY, tc_bps=0.0)
    res = run_backtest(pairs, cfg, data)
    assert np.allclose(res.book_beta, 0.0, atol=1e-9)
    # No beta to hedge, so the overlay is empty.
    assert np.allclose(res.positions.iloc[:, -1], 0.0, atol=1e-3)


def test_dollar_neutral_pair_has_residual_beta():
    data = make_market()
    pairs = [PairSpec("AAA", "BBB")]  # 1.2 vs 0.8 beta, equal dollars
    cfg = config_for(data, rebalance=RebalanceFreq.DAILY, tc_bps=0.0)
    res = run_backtest(pairs, cfg, data)
    # gross 2x NAV split evenly => net beta = 1.0 * 1.2 - 1.0 * 0.8 = 0.4
    assert res.book_beta.iloc[0] == pytest.approx(0.4, abs=1e-9)


def test_weights_allocate_gross():
    data = make_market()
    pairs = [PairSpec("AAA", "BBB", weight=3.0), PairSpec("CCC", "DDD", weight=1.0)]
    cfg = config_for(data, tc_bps=0.0)
    res = run_backtest(pairs, cfg, data)
    day0 = res.positions.iloc[0].abs()
    g1 = day0.iloc[0] + day0.iloc[1]
    g2 = day0.iloc[2] + day0.iloc[3]
    assert g1 / g2 == pytest.approx(3.0)
    assert (g1 + g2) == pytest.approx(2.0 * cfg.initial_capital)
