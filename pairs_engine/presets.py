"""Preset example pairs so students can start without typing tickers.

Each preset comes with a one-line rationale: why a PM might pair these two
names, and the obvious way the trade can go wrong.
"""

from __future__ import annotations

from dataclasses import dataclass

from .config import PairSpec


@dataclass(frozen=True)
class Preset:
    long: str
    short: str
    sector: str
    rationale: str

    def to_spec(self) -> PairSpec:
        return PairSpec(self.long, self.short)

    @property
    def label(self) -> str:
        return f"{self.long} / {self.short}"


PRESETS: list[Preset] = [
    Preset("KO", "PEP", "Consumer staples",
           "Cola duopoly with similar demand drivers. PEP's snacks business (Frito-Lay) is the main difference."),
    Preset("HD", "LOW", "Home improvement",
           "Two big-box home improvement chains driven by housing turnover and repair spending."),
    Preset("V", "MA", "Payments",
           "Card network duopoly. Very high correlation, so any spread usually reflects mix and cross-border exposure."),
    Preset("XOM", "CVX", "Energy",
           "Integrated oil majors. Both follow crude, but differ in refining, chemicals and project timing."),
    Preset("GM", "F", "Autos",
           "Detroit automakers. Cyclical, high beta, and sensitive to labor deals and EV strategy."),
    Preset("UPS", "FDX", "Transports",
           "Parcel delivery duopoly. Union contracts and Amazon volumes can split them sharply."),
    Preset("MSFT", "GOOGL", "Mega-cap tech",
           "Cloud and AI leaders. A looser pair whose businesses overlap only partly, which makes it a good 'is this really a pair?' case."),
]


def preset_by_label(label: str) -> Preset:
    for p in PRESETS:
        if p.label == label:
            return p
    raise KeyError(label)
