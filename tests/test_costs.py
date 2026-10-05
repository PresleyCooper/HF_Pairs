import numpy as np
import pandas as pd
import pytest

from pairs_engine import PairSpec, PriceData, RebalanceFreq, run_backtest
from pairs_engine.costs import borrow_fee, cash_interest, transaction_cost

from .conftest import config_for

CAP = 1_000_000.0


def test_unit_cost_functions():
    assert transaction_cost(1_000_000, 5) == pytest.approx(500.0)
    assert transaction_cost(-1_000_000, 5) == pytest.approx(500.0)
    assert borrow_fee(1_000_000, 0.0365, 10) == pytest.approx(1_000.0)
    assert cash_interest(1_000_000, 0.0365, 1) == pytest.approx(100.0)
    assert cash_interest(-1_000_000, 0.0365, 1) == pytest.approx(-100.0)


def flat_market(n: int = 200, dividend_day: int | None = None, div: float = 0.01) -> PriceData:
    """Prices that never move; optionally BBB pays a dividend on one day."""
    dates = pd.bdate_range("2021-01-01", periods=n)
    price = pd.DataFrame(100.0, index=dates, columns=["SPY", "AAA", "BBB"])
    total = price.copy()
    if dividend_day is not None:
        total.iloc[dividend_day:, total.columns.get_loc("BBB")] *= 1 + div
    return PriceData(price=price, total=total)


def run_flat(**kw):
    data = flat_market(**{k: kw.pop(k) for k in ("dividend_day", "div") if k in kw})
    cfg = config_for(data, rebalance=RebalanceFreq.NEVER, **kw)
    return run_backtest([PairSpec("AAA", "BBB")], cfg, data), cfg


def test_transaction_cost_on_initial_build():
    res, cfg = run_flat(tc_bps=10.0, borrow_rate=0.0, cash_rate=0.0)
    # 1m long + 1m short at 10bp = 2,000 (overlay is zero: flat prices -> no beta)
    assert res.trading_costs.iloc[0].sum() == pytest.approx(2_000.0)
    assert res.nav.iloc[-1] == pytest.approx(CAP - 2_000.0)


def test_borrow_accrues_on_calendar_days():
    res, cfg = run_flat(tc_bps=0.0, borrow_rate=0.01, cash_rate=0.0)
    days = (res.nav.index[-1] - res.nav.index[0]).days
    expected = 1_000_000.0 * 0.01 * days / 365
    assert res.borrow_costs.to_numpy().sum() == pytest.approx(expected)
    assert res.nav.iloc[-1] == pytest.approx(CAP - expected)


def test_cash_interest_on_short_proceeds():
    res, cfg = run_flat(tc_bps=0.0, borrow_rate=0.0, cash_rate=0.05)
    # Long 1m paid with cash, short proceeds of 1m add back: cash == NAV.
    gap = (res.nav.index[1] - res.nav.index[0]).days
    assert res.interest.iloc[1] == pytest.approx(CAP * 0.05 * gap / 365)
    assert res.nav.iloc[-1] > CAP


def test_negative_cash_pays_interest():
    # A 1.5x long SPY overlay on top of a cash-neutral pair book borrows cash.
    dates = pd.bdate_range("2021-01-01", periods=200)
    rm = np.r_[0.0, np.random.default_rng(0).normal(0, 0.01, 199)]
    spy = 100 * np.cumprod(1 + rm)
    data = PriceData.from_total(pd.DataFrame({"SPY": spy, "AAA": spy, "BBB": spy}, index=dates))
    cfg = config_for(data, target_beta=1.5, tc_bps=0.0, cash_rate=0.05,
                     rebalance=RebalanceFreq.NEVER)
    res = run_backtest([PairSpec("AAA", "BBB")], cfg, data)
    # Long 1m AAA, short 1m BBB, long 1.5m SPY -> cash = NAV - 1.5m < 0
    assert res.interest.iloc[1] < 0


def test_short_dividend_toggle():
    charged, _ = run_flat(tc_bps=0.0, borrow_rate=0.0, cash_rate=0.0,
                          dividend_day=150, charge_short_dividends=True)
    free, _ = run_flat(tc_bps=0.0, borrow_rate=0.0, cash_rate=0.0,
                       dividend_day=150, charge_short_dividends=False)
    # Short 1m of BBB pays a 1% dividend = 10,000 when charged.
    assert free.nav.iloc[-1] - charged.nav.iloc[-1] == pytest.approx(10_000.0)
    assert free.nav.iloc[-1] == pytest.approx(CAP)


def test_long_leg_always_receives_dividend():
    # Flip the pair so BBB (the dividend payer) is the long leg.
    data = flat_market(dividend_day=150)
    cfg = config_for(data, rebalance=RebalanceFreq.NEVER, tc_bps=0.0,
                     borrow_rate=0.0, cash_rate=0.0, charge_short_dividends=False)
    res = run_backtest([PairSpec("BBB", "AAA")], cfg, data)
    assert res.nav.iloc[-1] - CAP == pytest.approx(10_000.0)
