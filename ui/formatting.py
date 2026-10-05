"""Number formatting shared by the tabs."""

from __future__ import annotations

import math

import pandas as pd

from pairs_engine.analytics import STAT_FORMATS


def fmt_value(v: float, kind: str) -> str:
    if v is None or (isinstance(v, float) and not math.isfinite(v)):
        return "–"
    if kind == "pct":
        return f"{v:.1%}" if abs(v) >= 0.001 else f"{v:.2%}"
    return f"{v:.2f}"


def stats_table(columns: dict[str, dict[str, float]]) -> pd.DataFrame:
    """Side-by-side formatted stats: one column per run, one row per stat."""
    rows = {
        stat: {name: fmt_value(stats.get(stat, float("nan")), kind) for name, stats in columns.items()}
        for stat, kind in STAT_FORMATS.items()
    }
    return pd.DataFrame.from_dict(rows, orient="index")


def beta_label(b: float) -> str:
    return f"β = {b:+.2f}" if b else "β = 0 (market neutral)"
