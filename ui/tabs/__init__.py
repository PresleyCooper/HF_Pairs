"""One module per app tab. Each exposes ``render(ctx: RunContext)``."""

from __future__ import annotations

from dataclasses import dataclass

from pairs_engine import BacktestConfig, BacktestResult, PairSpec


@dataclass
class RunContext:
    pairs: list[PairSpec]
    config: BacktestConfig
    result: BacktestResult  # run at the user's target beta
    neutral: BacktestResult  # same book hedged to beta 0

    @property
    def is_neutral(self) -> bool:
        return self.config.target_beta == 0
