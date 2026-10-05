"""On-disk price cache so repeat runs don't hit Yahoo Finance.

Each ticker's *full* history is downloaded once a day and stored as a parquet
file. Any date range is then just a slice of that file, so moving the date
sliders in the app never triggers a new download.

``CachedDownloader`` has the same call signature as the downloader that
:func:`pairs_engine.data.load_prices` expects, so it plugs straight in.
"""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Callable

import pandas as pd

FULL_HISTORY_START = date(1990, 1, 1)
FIELDS = ("Adj Close", "Close")


class CachedDownloader:
    def __init__(
        self,
        cache_dir: str | Path = ".cache/prices",
        fetch: Callable[[list[str], date, date], pd.DataFrame] | None = None,
    ) -> None:
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._fetch = fetch or self._yf_fetch

    @staticmethod
    def _yf_fetch(tickers: list[str], start: date, end: date) -> pd.DataFrame:
        from .data import _yf_download

        return _yf_download(tickers, start, end)

    def _path(self, ticker: str) -> Path:
        safe = "".join(c if c.isalnum() or c in "-._^" else "_" for c in ticker)
        return self.cache_dir / f"{safe}.parquet"

    def _is_fresh(self, path: Path) -> bool:
        if not path.exists():
            return False
        return datetime.fromtimestamp(path.stat().st_mtime).date() == date.today()

    def _refresh(self, tickers: list[str]) -> None:
        raw = self._fetch(tickers, FULL_HISTORY_START, date.today())
        for t in tickers:
            cols = {}
            for fld in FIELDS:
                if raw is not None and (fld, t) in raw.columns:
                    cols[fld] = raw[(fld, t)]
            df = pd.DataFrame(cols).dropna(how="all") if cols else pd.DataFrame(columns=list(FIELDS))
            # An empty file still records "we asked today and got nothing", so a
            # bad ticker is not re-requested on every rerun.
            df.to_parquet(self._path(t))

    def __call__(self, tickers: list[str], start: date, end: date) -> pd.DataFrame:
        stale = [t for t in tickers if not self._is_fresh(self._path(t))]
        if stale:
            self._refresh(stale)
        cols = {}
        for t in tickers:
            df = pd.read_parquet(self._path(t))
            for fld in FIELDS:
                s = df[fld] if fld in df.columns else pd.Series(dtype=float)
                cols[(fld, t)] = s
        out = pd.DataFrame(cols)
        out.index = pd.DatetimeIndex(out.index).tz_localize(None)
        return out.loc[pd.Timestamp(start):pd.Timestamp(end)].sort_index()
