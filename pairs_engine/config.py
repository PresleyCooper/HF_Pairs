"""Configuration objects for the pairs backtest engine.

Everything the engine needs to know about *what* to trade (``PairSpec``) and
*how* to simulate it (``BacktestConfig``) lives here, as plain immutable
dataclasses. Keeping them immutable means a config can be hashed and cached by
the UI, and copied with ``dataclasses.replace`` to run variants (e.g. the
market-neutral comparison run).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date
from enum import Enum


class SizingMethod(str, Enum):
    """How the two legs of a pair are sized relative to each other.

    In every method the pair's *gross* notional (long + short) is fixed by its
    portfolio weight; the method only decides how that gross is split.
    """

    DOLLAR_NEUTRAL = "dollar_neutral"  # equal dollars long and short
    BETA_NEUTRAL = "beta_neutral"  # long * beta_long == short * beta_short
    VOL_MATCHED = "vol_matched"  # long * vol_long == short * vol_short

    @property
    def label(self) -> str:
        return {
            SizingMethod.DOLLAR_NEUTRAL: "Dollar neutral",
            SizingMethod.BETA_NEUTRAL: "Beta neutral",
            SizingMethod.VOL_MATCHED: "Volatility matched",
        }[self]


class RebalanceFreq(str, Enum):
    """How often positions are reset to their target sizes."""

    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    NEVER = "never"  # build on day one, then let everything drift


@dataclass(frozen=True)
class PairSpec:
    """One pairs trade: buy ``long``, sell short ``short``."""

    long: str
    short: str
    weight: float = 1.0
    sizing: SizingMethod = SizingMethod.DOLLAR_NEUTRAL

    def __post_init__(self) -> None:
        # Normalise tickers so "ko" and "KO " are the same instrument.
        object.__setattr__(self, "long", self.long.strip().upper())
        object.__setattr__(self, "short", self.short.strip().upper())
        object.__setattr__(self, "sizing", SizingMethod(self.sizing))
        if self.weight < 0:
            raise ValueError(f"Pair weight must be non-negative, got {self.weight}")
        if self.long == self.short:
            raise ValueError(f"Long and short legs must differ ({self.long})")

    @property
    def label(self) -> str:
        """Human-readable name, e.g. ``"KO / PEP"`` (long first)."""
        return f"{self.long} / {self.short}"

    def flipped(self) -> "PairSpec":
        """Same pair with the direction reversed (long becomes short)."""
        return replace(self, long=self.short, short=self.long)


@dataclass(frozen=True)
class BacktestConfig:
    """All simulation assumptions. Rates are annual decimals (0.02 == 2%)."""

    start: date
    end: date
    initial_capital: float = 1_000_000.0
    # Gross leverage of the *pair book* (sum of |long| + |short| over NAV).
    # The benchmark beta overlay sits outside this budget.
    gross_leverage: float = 2.0
    rebalance: RebalanceFreq = RebalanceFreq.MONTHLY
    tc_bps: float = 5.0  # cost per dollar traded, in basis points
    borrow_rate: float = 0.005  # annual fee on short stock notional
    etf_borrow_rate: float = 0.0025  # annual fee when the overlay is short the ETF
    cash_rate: float = 0.02  # earned on cash + short proceeds, paid if cash < 0
    charge_short_dividends: bool = True
    benchmark: str = "SPY"
    beta_window: int = 60  # trading days in the rolling regression
    target_beta: float = 0.0
    # Betas/vols below this are floored when sizing, so a near-zero or
    # negative estimate cannot create an absurdly large leg.
    sizing_floor: float = 0.1

    def __post_init__(self) -> None:
        object.__setattr__(self, "rebalance", RebalanceFreq(self.rebalance))
        object.__setattr__(self, "benchmark", self.benchmark.strip().upper())
        if self.end <= self.start:
            raise ValueError("End date must be after start date")
        if self.initial_capital <= 0:
            raise ValueError("Starting capital must be positive")
        if self.gross_leverage <= 0:
            raise ValueError("Gross leverage must be positive")
        if self.beta_window < 10:
            raise ValueError("Beta window must be at least 10 trading days")

    def with_target_beta(self, target_beta: float) -> "BacktestConfig":
        return replace(self, target_beta=target_beta)
