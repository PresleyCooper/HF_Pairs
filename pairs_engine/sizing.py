"""Leg sizing: how a pair's gross dollars are split between long and short.

All three methods keep the pair's *gross* exposure (long + short) fixed, so a
pair's weight in the portfolio means the same thing whatever the method.

* Dollar neutral: long = short. Simple, but if the short leg is a sleepier
  stock than the long leg the pair still carries market risk.
* Beta neutral: long * beta_L = short * beta_S, so the pair's net beta is
  zero.
* Volatility matched: long * vol_L = short * vol_S, so each leg contributes
  the same stand-alone risk.

The beta- and vol-based methods solve ``long * x_L = short * x_S`` with
``long + short = G``, which gives::

    long  = G * x_S / (x_L + x_S)
    short = G * x_L / (x_L + x_S)
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .config import SizingMethod


@dataclass(frozen=True)
class LegSizes:
    """Unsigned dollar notionals for one pair, plus any sizing caveats."""

    long: float
    short: float
    floored: bool = False  # an estimate was below the floor and was raised
    fallback: bool = False  # estimates were missing; fell back to dollar neutral


def _split(gross: float, x_long: float, x_short: float) -> tuple[float, float]:
    total = x_long + x_short
    return gross * x_short / total, gross * x_long / total


def size_pair(
    method: SizingMethod,
    gross: float,
    beta_long: float = math.nan,
    beta_short: float = math.nan,
    vol_long: float = math.nan,
    vol_short: float = math.nan,
    floor: float = 0.1,
) -> LegSizes:
    """Split ``gross`` dollars between the long and short leg.

    Betas or vols below ``floor`` (including negative betas) are raised to
    ``floor``. Without that, a stock whose estimated beta is 0.01 would be
    sized at 100x its partner. If estimates are missing, the pair falls back
    to dollar neutral and is flagged.
    """
    if gross < 0:
        raise ValueError("gross must be non-negative")
    method = SizingMethod(method)

    if method is SizingMethod.DOLLAR_NEUTRAL:
        return LegSizes(gross / 2, gross / 2)

    if method is SizingMethod.BETA_NEUTRAL:
        x_long, x_short = beta_long, beta_short
    else:
        x_long, x_short = vol_long, vol_short

    if not (math.isfinite(x_long) and math.isfinite(x_short)):
        return LegSizes(gross / 2, gross / 2, fallback=True)

    floored = x_long < floor or x_short < floor
    x_long, x_short = max(x_long, floor), max(x_short, floor)
    long_, short_ = _split(gross, x_long, x_short)
    return LegSizes(long_, short_, floored=floored)
