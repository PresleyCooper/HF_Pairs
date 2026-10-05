"""Save and load a portfolio of pairs (plus its assumptions) as JSON.

The format is deliberately readable, so students can share portfolios
or edit them by hand::

    {
      "format": "hf-pairs-portfolio",
      "version": 1,
      "pairs": [{"long": "KO", "short": "PEP", "weight": 1.0, "sizing": "dollar_neutral"}],
      "config": {"start": "2015-01-01", "end": "2024-12-31", "target_beta": 0.0, ...}
    }

``config`` is optional when loading. Any field left out keeps its default.
"""

from __future__ import annotations

import json
from dataclasses import fields
from datetime import date
from enum import Enum
from typing import Any

from .config import BacktestConfig, PairSpec, RebalanceFreq, SizingMethod

FORMAT = "hf-pairs-portfolio"
VERSION = 1


def _jsonable(v: Any) -> Any:
    if isinstance(v, Enum):
        return v.value
    if isinstance(v, date):
        return v.isoformat()
    return v


def config_to_dict(cfg: BacktestConfig) -> dict[str, Any]:
    return {f.name: _jsonable(getattr(cfg, f.name)) for f in fields(cfg)}


def config_from_dict(d: dict[str, Any]) -> BacktestConfig:
    known = {f.name for f in fields(BacktestConfig)}
    unknown = set(d) - known
    if unknown:
        raise ValueError(f"Unknown config fields: {', '.join(sorted(unknown))}")
    kw = dict(d)
    for k in ("start", "end"):
        if k in kw:
            kw[k] = date.fromisoformat(kw[k])
    if "rebalance" in kw:
        kw["rebalance"] = RebalanceFreq(kw["rebalance"])
    if "start" not in kw or "end" not in kw:
        raise ValueError("config needs both 'start' and 'end'")
    return BacktestConfig(**kw)


def to_json(pairs: list[PairSpec], config: BacktestConfig | None = None) -> str:
    doc: dict[str, Any] = {
        "format": FORMAT,
        "version": VERSION,
        "pairs": [
            {"long": p.long, "short": p.short, "weight": p.weight, "sizing": p.sizing.value}
            for p in pairs
        ],
    }
    if config is not None:
        doc["config"] = config_to_dict(config)
    return json.dumps(doc, indent=2)


def from_json(text: str) -> tuple[list[PairSpec], BacktestConfig | None]:
    """Parse a saved portfolio. Raises ValueError with a readable message if invalid."""
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Not valid JSON: {exc}") from exc
    if not isinstance(doc, dict) or doc.get("format") != FORMAT:
        raise ValueError("This file is not an HF Pairs portfolio.")
    if doc.get("version", 1) > VERSION:
        raise ValueError("This portfolio was saved by a newer version of the app.")
    raw_pairs = doc.get("pairs")
    if not isinstance(raw_pairs, list) or not raw_pairs:
        raise ValueError("The portfolio has no pairs.")
    pairs = []
    for i, p in enumerate(raw_pairs, start=1):
        try:
            pairs.append(PairSpec(
                long=str(p["long"]), short=str(p["short"]),
                weight=float(p.get("weight", 1.0)),
                sizing=SizingMethod(p.get("sizing", SizingMethod.DOLLAR_NEUTRAL.value)),
            ))
        except (KeyError, ValueError, TypeError) as exc:
            raise ValueError(f"Pair {i} is invalid: {exc}") from exc
    config = None
    if doc.get("config") is not None:
        try:
            config = config_from_dict(doc["config"])
        except (ValueError, TypeError) as exc:
            raise ValueError(f"Settings are invalid: {exc}") from exc
    return pairs, config
