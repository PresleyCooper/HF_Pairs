"""Price data container, yfinance loader, and pair validation.

Two price series are kept for every ticker:

* ``price`` - the close adjusted for splits only. Its returns are pure price
  moves and ignore dividends.
* ``total`` - the close adjusted for splits *and* dividends (yfinance's
  "Adj Close"). Its returns are total returns.

The difference between the two is the dividend. A long position earns total
return. A short position *pays* the dividend to the stock lender, so it is
charged total return. The ``charge_short_dividends`` switch lets students see
what happens if you (wrongly) ignore that.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Callable, Iterable

import numpy as np
import pandas as pd

from .config import PairSpec

TRADING_DAYS_PER_YEAR = 252
# Warn when a gap in a ticker's history is longer than this many trading days.
MAX_FFILL_DAYS = 5
# Warn when a pair has less than this much overlapping history in the window.
MIN_RECOMMENDED_OBS = TRADING_DAYS_PER_YEAR


@dataclass
class PriceData:
    """Aligned daily prices for a set of tickers (columns) on one calendar."""

    price: pd.DataFrame
    total: pd.DataFrame

    def __post_init__(self) -> None:
        if not self.price.index.equals(self.total.index):
            raise ValueError("price and total must share an index")
        if list(self.price.columns) != list(self.total.columns):
            raise ValueError("price and total must share columns")
        self.price = self.price.sort_index()
        self.total = self.total.sort_index()

    @classmethod
    def from_total(cls, total: pd.DataFrame) -> "PriceData":
        """Build from a single series per ticker (no dividends). Handy in tests."""
        return cls(price=total.copy(), total=total.copy())

    @property
    def tickers(self) -> list[str]:
        return list(self.price.columns)

    @property
    def index(self) -> pd.DatetimeIndex:
        return self.price.index

    def total_returns(self) -> pd.DataFrame:
        return self.total.pct_change(fill_method=None)

    def price_returns(self) -> pd.DataFrame:
        return self.price.pct_change(fill_method=None)

    def first_valid(self, ticker: str) -> pd.Timestamp | None:
        return self.total[ticker].first_valid_index()

    def subset(self, tickers: Iterable[str]) -> "PriceData":
        cols = list(dict.fromkeys(tickers))
        return PriceData(price=self.price[cols], total=self.total[cols])


@dataclass
class LoadResult:
    """Output of :func:`load_prices`: the data plus anything the user should know."""

    data: PriceData
    missing: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def warmup_start(start: date, beta_window: int) -> date:
    """Calendar date far enough before ``start`` to fill the rolling window.

    Roughly 1.5 calendar days per trading day plus a month of slack covers
    weekends and holidays.
    """
    return start - timedelta(days=int(beta_window * 1.5) + 30)


def _yf_download(tickers: list[str], start: date, end: date) -> pd.DataFrame:
    import yfinance as yf  # imported lazily so tests never need the network

    return yf.download(
        tickers,
        start=start.isoformat(),
        # yfinance treats ``end`` as exclusive
        end=(end + timedelta(days=1)).isoformat(),
        auto_adjust=False,
        actions=False,
        progress=False,
        multi_level_index=True,
        threads=True,
    )


def load_prices(
    tickers: Iterable[str],
    start: date,
    end: date,
    calendar_ticker: str,
    downloader: Callable[[list[str], date, date], pd.DataFrame] | None = None,
) -> LoadResult:
    """Download and align prices for ``tickers`` between ``start`` and ``end``.

    ``start`` should already include any warm-up period (see
    :func:`warmup_start`). ``calendar_ticker`` (the benchmark) defines the
    trading calendar; every other ticker is aligned to its dates.

    Short gaps are forward-filled (a stale price means a zero return that day).
    Gaps longer than ``MAX_FFILL_DAYS`` are still filled so positions can be
    valued, but they produce a warning. Dates before a ticker's first price
    (e.g. before its IPO) stay empty.
    """
    downloader = downloader or _yf_download
    wanted = list(dict.fromkeys([t.strip().upper() for t in tickers] + [calendar_ticker]))
    raw = downloader(wanted, start, end)

    warnings: list[str] = []
    missing: list[str] = []
    if raw is None or raw.empty:
        raise ValueError("No price data returned. Check your internet connection and tickers.")

    adj = raw["Adj Close"] if "Adj Close" in raw.columns.get_level_values(0) else raw["Close"]
    close = raw["Close"]
    adj = adj.reindex(columns=wanted)
    close = close.reindex(columns=wanted)

    for t in wanted:
        if adj[t].dropna().empty:
            missing.append(t)
    if calendar_ticker in missing:
        raise ValueError(f"Could not load benchmark {calendar_ticker}; cannot build a calendar.")

    calendar = adj[calendar_ticker].dropna().index
    keep = [t for t in wanted if t not in missing]
    adj = adj.loc[calendar, keep]
    close = close.loc[calendar, keep]

    for t in keep:
        first = adj[t].first_valid_index()
        tail = adj.loc[first:, t]
        # Longest run of consecutive missing values after the first price.
        isna = tail.isna().to_numpy()
        longest = _longest_run(isna)
        if longest > MAX_FFILL_DAYS:
            warnings.append(
                f"{t}: {longest} consecutive trading days with no price were "
                "forward-filled (stale prices mean zero returns on those days)."
            )
        adj.loc[first:, t] = tail.ffill()
        close.loc[first:, t] = close.loc[first:, t].ffill()
        # If the raw close is missing where adj close exists, fall back to adj.
        close[t] = close[t].fillna(adj[t])

    adj.index = pd.DatetimeIndex(adj.index).tz_localize(None)
    close.index = adj.index
    adj.index.name = close.index.name = "Date"
    return LoadResult(data=PriceData(price=close, total=adj), missing=missing, warnings=warnings)


def _longest_run(mask: np.ndarray) -> int:
    best = cur = 0
    for v in mask:
        cur = cur + 1 if v else 0
        best = max(best, cur)
    return best


@dataclass
class PairAvailability:
    """How much usable history a pair has inside the backtest window."""

    pair: PairSpec
    first_tradable: pd.Timestamp | None
    n_obs: int
    warnings: list[str]

    @property
    def usable(self) -> bool:
        return self.first_tradable is not None


def check_pair_history(
    pairs: Iterable[PairSpec],
    data: PriceData,
    start: date,
    end: date,
    beta_window: int,
) -> list[PairAvailability]:
    """Report when each pair becomes tradable and warn on short histories.

    A pair is tradable once both legs have at least ``beta_window`` returns,
    because every sizing method and the beta overlay need a beta estimate.
    """
    out: list[PairAvailability] = []
    start_ts, end_ts = pd.Timestamp(start), pd.Timestamp(end)
    for p in pairs:
        warns: list[str] = []
        absent = [t for t in (p.long, p.short) if t not in data.tickers]
        if absent:
            warns.append(f"No data for {', '.join(absent)}; pair skipped.")
            out.append(PairAvailability(p, None, 0, warns))
            continue

        both = data.total[[p.long, p.short]].notna().all(axis=1)
        # The first date with a full window of returns for both legs.
        counts = both.cumsum()
        ready = counts[counts > beta_window]
        if ready.empty:
            warns.append("Not enough history to estimate betas; pair skipped.")
            out.append(PairAvailability(p, None, 0, warns))
            continue
        first_tradable = max(ready.index[0], start_ts)
        in_window = both[(both.index >= first_tradable) & (both.index <= end_ts)]
        n_obs = int(in_window.sum())
        if n_obs == 0:
            warns.append("No overlapping history inside the backtest window; pair skipped.")
            out.append(PairAvailability(p, None, 0, warns))
            continue
        if first_tradable > start_ts + pd.Timedelta(days=7):
            warns.append(
                f"Only tradable from {first_tradable.date()} (needs {beta_window} days of "
                "history for both legs). It joins the book at the next rebalance."
            )
        if n_obs < MIN_RECOMMENDED_OBS:
            warns.append(
                f"Only {n_obs} trading days of history in the window; "
                "statistics will be noisy."
            )
        out.append(PairAvailability(p, first_tradable, n_obs, warns))
    return out
