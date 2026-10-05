import numpy as np
import pandas as pd
import pytest

from pairs_engine import PairSpec, RebalanceFreq, run_backtest
from pairs_engine.analytics import (
    drawdown,
    drawdown_breakdown,
    leg_attribution,
    pair_attribution,
    pair_returns,
    summary_stats,
    worst_drawdown,
)

from .conftest import config_for, make_market


def test_drawdown_and_window():
    idx = pd.bdate_range("2022-01-03", periods=6)
    nav = pd.Series([100, 120, 90, 110, 125, 100], index=idx, dtype=float)
    assert drawdown(nav).min() == pytest.approx(-0.25)
    w = worst_drawdown(nav)
    assert (w.peak, w.trough, w.recovery) == (idx[1], idx[2], idx[4])
    assert w.depth == pytest.approx(-0.25)


def test_sharpe_sortino_hit_rate_on_known_series():
    idx = pd.bdate_range("2022-01-03", periods=200)
    r = pd.Series(np.tile([0.01, -0.005], 100), index=idx)
    b = pd.Series(0.0, index=idx)
    s = summary_stats(r, b, rf_annual=0.0)
    expected_sharpe = r.mean() / r.std(ddof=1) * np.sqrt(252)
    assert s["Sharpe ratio"] == pytest.approx(expected_sharpe)
    downside = np.sqrt(np.mean(np.minimum(r, 0) ** 2))
    assert s["Sortino ratio"] == pytest.approx(r.mean() / downside * np.sqrt(252))
    assert s["Hit rate (daily)"] == pytest.approx(0.5)
    assert s["Win/loss ratio"] == pytest.approx(2.0)


def test_beta_and_alpha_recovered():
    rng = np.random.default_rng(0)
    idx = pd.bdate_range("2020-01-01", periods=2000)
    b = pd.Series(rng.normal(0.0003, 0.01, 2000), index=idx)
    r = 0.0002 + 0.7 * b  # no noise: alpha 2bp/day, beta 0.7
    s = summary_stats(r, b, rf_annual=0.0)
    assert s["Realized beta"] == pytest.approx(0.7)
    assert s["Alpha (annualized)"] == pytest.approx(0.0002 * 252)
    assert s["Correlation to benchmark"] == pytest.approx(1.0)


@pytest.fixture
def result():
    data = make_market(idio=0.01, seed=2)
    pairs = [PairSpec("AAA", "BBB"), PairSpec("CCC", "DDD", weight=2.0)]
    cfg = config_for(data, target_beta=0.3, rebalance=RebalanceFreq.WEEKLY,
                     tc_bps=5.0, borrow_rate=0.01, cash_rate=0.03)
    return run_backtest(pairs, cfg, data)


def test_attribution_reconciles_to_nav(result):
    change = result.nav.iloc[-1] - result.config.initial_capital
    assert pair_attribution(result)["Net P&L"].sum() == pytest.approx(change)
    assert leg_attribution(result).sum() == pytest.approx(change)


def test_returns_compound_to_nav(result):
    compounded = result.config.initial_capital * (1 + result.returns).prod()
    assert compounded == pytest.approx(result.nav.iloc[-1])


def test_pair_returns_shape(result):
    pr = pair_returns(result)
    assert list(pr.columns) == result.pair_names
    assert pr.notna().all().all()


def test_drawdown_breakdown_sorted_worst_first(result):
    win, contrib = drawdown_breakdown(result)
    assert win.depth < 0
    assert contrib.is_monotonic_increasing
    # Contributions during the window reconcile to the NAV move.
    move = result.nav.loc[win.trough] - result.nav.loc[win.peak]
    assert contrib.sum() == pytest.approx(move)


def test_daily_report_columns(result):
    from pairs_engine.analytics import daily_report

    rep = daily_report(result)
    assert len(rep) == len(result.nav)
    assert "AAA / BBB net P&L" in rep.columns and "NAV" in rep.columns
    pnl_cols = [c for c in rep.columns if c.endswith("net P&L")]
    total = rep[pnl_cols].sum().sum() + rep["Cash interest"].sum()
    assert total == pytest.approx(result.nav.iloc[-1] - result.config.initial_capital)
