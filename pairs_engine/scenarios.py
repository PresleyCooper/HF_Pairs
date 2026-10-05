"""Historical stress windows.

Each scenario re-runs the *same* book (pairs and assumptions) over a fixed
historical window, independent of the user's chosen dates. Pairs whose stocks
did not trade yet (e.g. V before its 2008 IPO, GM between its 2009
bankruptcy and 2010 relisting) are skipped and reported. Note that Yahoo
Finance has no data for delisted companies at all, so these windows suffer
from survivorship bias too.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date

from .analytics import result_stats, summary_stats
from .backtest import BacktestResult, run_backtest
from .config import BacktestConfig, PairSpec
from .data import PriceData


@dataclass(frozen=True)
class Scenario:
    name: str
    start: date
    end: date
    description: str


SCENARIOS: list[Scenario] = [
    Scenario(
        "2008 financial crisis", date(2008, 9, 1), date(2009, 3, 9),
        "Lehman fails, credit freezes, and the S&P 500 falls about 45% to its March 2009 low. "
        "Short-sale bans on financials and violent short squeezes hit many long/short funds.",
    ),
    Scenario(
        "COVID crash (Feb-Mar 2020)", date(2020, 2, 19), date(2020, 3, 23),
        "The fastest 30%+ bear market on record. Correlations jump toward 1 and liquidity "
        "dries up. Travel, energy and anything leveraged is hit hardest.",
    ),
    Scenario(
        "2022 bear market", date(2022, 1, 3), date(2022, 10, 12),
        "Inflation and the fastest Fed hiking cycle in decades. Long-duration growth stocks "
        "fall hardest, while energy and value hold up.",
    ),
    Scenario(
        "Value vs growth rotation (Nov 2020-Mar 2021)", date(2020, 11, 9), date(2021, 3, 31),
        "Pfizer's vaccine announcement on 9 Nov 2020 triggers a sharp rotation out of "
        "pandemic winners and momentum stocks into cheap cyclicals. Pairs that are long "
        "growth and short value get hurt.",
    ),
]


@dataclass
class ScenarioOutcome:
    scenario: Scenario
    result: BacktestResult | None = None
    neutral: BacktestResult | None = None
    stats: dict[str, float] = field(default_factory=dict)
    neutral_stats: dict[str, float] = field(default_factory=dict)
    bench_stats: dict[str, float] = field(default_factory=dict)
    skipped: list[str] = field(default_factory=list)
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.result is not None and bool(self.result.pairs)


def scenario_config(base: BacktestConfig, scenario: Scenario) -> BacktestConfig:
    return replace(base, start=scenario.start, end=scenario.end)


def run_scenario(
    pairs: list[PairSpec],
    base: BacktestConfig,
    data: PriceData,
    scenario: Scenario,
) -> ScenarioOutcome:
    """Run the book over ``scenario``. ``data`` must cover it, including warm-up."""
    cfg = scenario_config(base, scenario)
    out = ScenarioOutcome(scenario)
    try:
        res = run_backtest(pairs, cfg, data)
    except ValueError as exc:
        out.error = str(exc)
        return out
    out.skipped = [a.pair.label for a in res.availability if not a.usable]
    # A pair that only becomes tradable partway through the window is also
    # effectively missing for a short stress test.
    late = [a.pair.label for a in res.availability
            if a.usable and a.first_tradable is not None and a.first_tradable.date() > scenario.start]
    out.skipped += [f"{name} (joined late)" for name in late]
    if not res.pairs:
        out.error = "None of the pairs traded during this window."
        return out
    neutral = res if cfg.target_beta == 0 else run_backtest(pairs, cfg.with_target_beta(0.0), data)
    out.result, out.neutral = res, neutral
    out.stats = result_stats(res)
    out.neutral_stats = result_stats(neutral)
    out.bench_stats = summary_stats(res.bench_returns, res.bench_returns, cfg.cash_rate)
    return out


def worst_pair(result: BacktestResult) -> tuple[str, float]:
    """The pair with the lowest net P&L over the whole run, and that P&L."""
    totals = result.pair_pnl()[result.pair_names].sum()
    name = totals.idxmin()
    return name, float(totals[name])

