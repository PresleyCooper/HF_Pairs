from datetime import date

import numpy as np
import pandas as pd
import pytest

from pairs_engine import PairSpec, load_prices
from pairs_engine.data import check_pair_history


def fake_downloader(frames: dict[str, pd.Series]):
    """Mimic yfinance's MultiIndex (field, ticker) output."""

    def _dl(tickers, start, end):
        cols = {}
        for t in tickers:
            s = frames.get(t)
            for fld in ("Adj Close", "Close"):
                cols[(fld, t)] = s if s is not None else pd.Series(np.nan, index=frames["SPY"].index)
        return pd.DataFrame(cols)

    return _dl


def test_loader_flags_missing_and_gaps():
    idx = pd.bdate_range("2023-01-02", periods=100)
    spy = pd.Series(np.linspace(100, 110, 100), index=idx)
    gappy = spy.copy()
    gappy.iloc[40:50] = np.nan  # 10-day hole
    late = spy.copy()
    late.iloc[:30] = np.nan  # "IPO" on day 30
    dl = fake_downloader({"SPY": spy, "GAP": gappy, "LATE": late})
    res = load_prices(["GAP", "LATE", "NOPE"], date(2023, 1, 1), date(2023, 6, 1), "SPY", dl)
    assert res.missing == ["NOPE"]
    assert any("GAP" in w and "10" in w for w in res.warnings)
    # Gap filled, pre-IPO left empty.
    assert res.data.total["GAP"].iloc[40:50].notna().all()
    assert res.data.total["LATE"].iloc[:30].isna().all()


def test_loader_requires_benchmark():
    idx = pd.bdate_range("2023-01-02", periods=10)
    dl = fake_downloader({"SPY": pd.Series(np.nan, index=idx), "AAA": pd.Series(1.0, index=idx)})
    with pytest.raises(ValueError):
        load_prices(["AAA"], date(2023, 1, 1), date(2023, 2, 1), "SPY", dl)


def test_pair_history_warnings():
    idx = pd.bdate_range("2023-01-02", periods=300)
    spy = pd.Series(np.linspace(100, 130, 300), index=idx)
    late = spy.copy()
    late.iloc[:200] = np.nan
    dl = fake_downloader({"SPY": spy, "AAA": spy * 1.01, "LATE": late})
    data = load_prices(["AAA", "LATE"], idx[0].date(), idx[-1].date(), "SPY", dl).data
    out = check_pair_history(
        [PairSpec("AAA", "LATE"), PairSpec("AAA", "SPY"), PairSpec("AAA", "ZZZ")],
        data, idx[70].date(), idx[-1].date(), beta_window=60,
    )
    late_pair, ok_pair, missing_pair = out
    assert late_pair.usable and late_pair.first_tradable == idx[260]  # 60 returns need 61 prices
    assert any("Only tradable from" in w for w in late_pair.warnings)
    assert any("trading days of history" in w for w in late_pair.warnings)
    assert ok_pair.usable
    assert not missing_pair.usable
