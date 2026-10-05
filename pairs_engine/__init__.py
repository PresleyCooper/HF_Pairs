"""Pairs trading backtest engine.

A pure-Python package with no UI dependencies. The typical flow is::

    from pairs_engine import PairSpec, BacktestConfig, load_prices, run_backtest

    pairs = [PairSpec("KO", "PEP")]
    cfg = BacktestConfig(start=date(2015, 1, 1), end=date(2024, 12, 31))
    loaded = load_prices(["KO", "PEP"], warmup_start(cfg.start, cfg.beta_window),
                         cfg.end, calendar_ticker=cfg.benchmark)
    result = run_backtest(pairs, cfg, loaded.data)
"""

from .backtest import OVERLAY, BacktestResult, run_backtest
from .config import BacktestConfig, PairSpec, RebalanceFreq, SizingMethod
from .data import LoadResult, PriceData, load_prices, warmup_start

__all__ = [
    "OVERLAY",
    "BacktestConfig",
    "BacktestResult",
    "LoadResult",
    "PairSpec",
    "PriceData",
    "RebalanceFreq",
    "SizingMethod",
    "load_prices",
    "run_backtest",
    "warmup_start",
]
