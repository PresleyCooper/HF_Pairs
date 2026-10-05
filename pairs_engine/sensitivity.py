"""How results change as the target beta slider moves.

Re-runs the same book across a grid of target betas. The pairs and costs are
identical in every run; only the size of the benchmark overlay changes. So
the curve isolates what market exposure alone did to risk-adjusted returns.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .analytics import result_stats
from .backtest import run_backtest
from .config import BacktestConfig, PairSpec
from .data import PriceData

DEFAULT_BETAS: tuple[float, ...] = tuple(np.round(np.arange(-0.5, 1.5001, 0.1), 2))
SWEEP_COLUMNS = ["Sharpe ratio", "CAGR", "Annualized volatility", "Max drawdown", "Realized beta"]


def beta_sweep(
    pairs: list[PairSpec],
    config: BacktestConfig,
    data: PriceData,
    betas: tuple[float, ...] = DEFAULT_BETAS,
) -> pd.DataFrame:
    """One row per target beta with the headline stats of that run."""
    rows = {}
    for b in betas:
        stats = result_stats(run_backtest(pairs, config.with_target_beta(float(b)), data))
        rows[float(b)] = {k: stats[k] for k in SWEEP_COLUMNS}
    df = pd.DataFrame.from_dict(rows, orient="index")
    df.index.name = "Target beta"
    return df
