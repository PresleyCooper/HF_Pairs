import numpy as np
import pytest

from pairs_engine import PairSpec, RebalanceFreq, run_backtest
from pairs_engine.analytics import summary_stats

from .conftest import config_for, make_market

PAIRS = [PairSpec("AAA", "BBB"), PairSpec("DDD", "CCC")]


@pytest.mark.parametrize("target", [-0.5, 0.0, 1.0, 1.5])
def test_overlay_hits_target_beta(target):
    data = make_market()
    cfg = config_for(data, target_beta=target, rebalance=RebalanceFreq.DAILY,
                     tc_bps=0.0, borrow_rate=0.0, etf_borrow_rate=0.0, cash_rate=0.0)
    res = run_backtest(PAIRS, cfg, data)
    # Ex-ante beta after each daily rebalance is exactly the target...
    assert np.allclose(res.total_beta, target, atol=1e-9)
    # ...and the realised (ex-post) regression beta matches it too.
    stats = summary_stats(res.returns.iloc[1:], res.bench_returns.iloc[1:])
    assert stats["Realized beta"] == pytest.approx(target, abs=1e-6)


def test_overlay_sits_outside_gross_budget():
    data = make_market()
    for target in (0.0, 1.5):
        cfg = config_for(data, target_beta=target, tc_bps=0.0)
        res = run_backtest(PAIRS, cfg, data)
        day0 = res.positions.iloc[0]
        pair_gross = day0.iloc[:-1].abs().sum()
        assert pair_gross == pytest.approx(cfg.gross_leverage * cfg.initial_capital)
        expected_overlay = (target - res.book_beta.iloc[0]) * res.nav.iloc[0]
        assert day0.iloc[-1] == pytest.approx(expected_overlay)


def test_never_rebalance_lets_hedge_drift():
    data = make_market(idio=0.01, seed=3)
    cfg = config_for(data, rebalance=RebalanceFreq.NEVER, target_beta=0.0)
    res = run_backtest(PAIRS, cfg, data)
    assert len(res.rebalance_dates) == 1
    assert res.total_beta.iloc[0] == pytest.approx(0.0, abs=1e-9)
    # Positions drift, so the ex-ante beta wanders away from the target.
    assert res.total_beta.abs().max() > 0.01


def test_rebalance_schedules():
    data = make_market(n=300)
    counts = {}
    for freq in RebalanceFreq:
        cfg = config_for(data, rebalance=freq)
        counts[freq] = len(run_backtest(PAIRS, cfg, data).rebalance_dates)
    n_days = 300 - 100
    assert counts[RebalanceFreq.DAILY] == n_days
    assert counts[RebalanceFreq.NEVER] == 1
    assert counts[RebalanceFreq.MONTHLY] < counts[RebalanceFreq.WEEKLY] < n_days
