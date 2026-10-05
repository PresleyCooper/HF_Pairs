"""Scenarios, beta sweep and JSON save/load."""

from datetime import date

import numpy as np
import pandas as pd
import pytest

from pairs_engine import BacktestConfig, PairSpec, PriceData, RebalanceFreq, SizingMethod, run_backtest
from pairs_engine.analytics import result_stats
from pairs_engine.portfolio_io import from_json, to_json
from pairs_engine.scenarios import Scenario, run_scenario
from pairs_engine.sensitivity import beta_sweep

from .conftest import config_for, make_market

PAIRS = [PairSpec("AAA", "BBB"), PairSpec("CCC", "DDD", weight=2, sizing=SizingMethod.BETA_NEUTRAL)]


def test_beta_sweep_matches_individual_runs():
    data = make_market(idio=0.01, seed=8)
    cfg = config_for(data, rebalance=RebalanceFreq.WEEKLY)
    sweep = beta_sweep(PAIRS, cfg, data, betas=(0.0, 0.5, 1.0))
    single = result_stats(run_backtest(PAIRS, cfg.with_target_beta(0.5), data))
    assert sweep.loc[0.5, "Sharpe ratio"] == pytest.approx(single["Sharpe ratio"])
    assert sweep["Realized beta"].is_monotonic_increasing


def test_scenario_skips_pairs_that_did_not_exist():
    data = make_market(n=400, idio=0.01)
    total = data.total.copy()
    total.iloc[:300, total.columns.get_loc("DDD")] = np.nan  # "IPO" on day 300
    data = PriceData.from_total(total)
    idx = data.index
    cfg = config_for(data)
    sc = Scenario("test", idx[150].date(), idx[250].date(), "")
    out = run_scenario(PAIRS, cfg, data, sc)
    assert out.ok
    assert out.result.pair_names == ["AAA / BBB"]
    assert any("CCC / DDD" in s for s in out.skipped)
    assert np.isfinite(out.stats["Total return"])


def test_scenario_with_no_tradable_pairs_reports_error():
    data = make_market(n=300)
    idx = data.index
    cfg = config_for(data)
    sc = Scenario("too early", idx[5].date(), idx[40].date(), "")  # no warm-up history
    out = run_scenario(PAIRS, cfg, data, sc)
    assert not out.ok and out.error


def test_json_round_trip():
    cfg = BacktestConfig(start=date(2015, 1, 1), end=date(2024, 6, 30), target_beta=0.35,
                         rebalance=RebalanceFreq.WEEKLY, tc_bps=7.5, benchmark="qqq")
    text = to_json(PAIRS, cfg)
    pairs, cfg2 = from_json(text)
    assert pairs == PAIRS
    assert cfg2 == cfg


def test_json_without_config_and_bad_input():
    pairs, cfg = from_json('{"format": "hf-pairs-portfolio", "pairs": [{"long": "ko", "short": "pep"}]}')
    assert pairs == [PairSpec("KO", "PEP")] and cfg is None
    for bad in ("not json", '{"format": "other"}', '{"format": "hf-pairs-portfolio", "pairs": []}',
                '{"format": "hf-pairs-portfolio", "pairs": [{"long": "KO"}]}',
                '{"format": "hf-pairs-portfolio", "pairs": [{"long": "KO", "short": "PEP"}], '
                '"config": {"start": "2020-01-01", "end": "2021-01-01", "bogus": 1}}'):
        with pytest.raises(ValueError):
            from_json(bad)
