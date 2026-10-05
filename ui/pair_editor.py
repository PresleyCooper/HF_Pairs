"""Editable table of pairs, with presets, one-click flips and equal weighting.

State model: ``st.session_state.pairs_df`` is the table the editor starts
from. The editor's live output is kept in ``pairs_current``. Buttons
(preset, flip, equal weight) rewrite ``pairs_df`` from ``pairs_current`` and
bump ``editor_ver``. That gives the editor a fresh key, so it redraws from
the new table instead of replaying stale cell edits.
"""

from __future__ import annotations

import math

import pandas as pd
import streamlit as st

from pairs_engine import PairSpec, SizingMethod
from pairs_engine.presets import PRESETS, preset_by_label

from .glossary import tip

COLUMNS = ["Long", "Short", "Weight", "Sizing"]
SIZING_LABELS = {m.label: m for m in SizingMethod}
ALL_PRESETS = "All seven presets"


def _row(long: str, short: str, weight: float = 1.0, sizing: str = SizingMethod.DOLLAR_NEUTRAL.label) -> dict:
    return {"Long": long, "Short": short, "Weight": weight, "Sizing": sizing}


def _default_table() -> pd.DataFrame:
    return pd.DataFrame([_row("KO", "PEP")], columns=COLUMNS)


def _init_state() -> None:
    ss = st.session_state
    if "pairs_df" not in ss:
        ss.pairs_df = _default_table()
        ss.pairs_current = ss.pairs_df
        ss.editor_ver = 0


def set_table(df: pd.DataFrame) -> None:
    """Replace the whole table (used by presets, flips and JSON load)."""
    ss = st.session_state
    ss.pairs_df = df.reset_index(drop=True)[COLUMNS]
    ss.pairs_current = ss.pairs_df
    ss.editor_ver += 1


def _current() -> pd.DataFrame:
    return st.session_state.pairs_current.copy().reset_index(drop=True)


# ---- Button callbacks (run before the next script pass) ----

def _add_preset() -> None:
    choice = st.session_state.preset_choice
    df = _current()
    chosen = PRESETS if choice == ALL_PRESETS else [preset_by_label(choice)]
    existing = {(str(r.Long).upper(), str(r.Short).upper()) for r in df.itertuples()}
    new = [_row(p.long, p.short) for p in chosen if (p.long, p.short) not in existing]
    set_table(pd.concat([df, pd.DataFrame(new, columns=COLUMNS)], ignore_index=True))


def _flip(i: int) -> None:
    df = _current()
    df.loc[i, ["Long", "Short"]] = df.loc[i, ["Short", "Long"]].to_numpy()
    set_table(df)


def _equal_weight() -> None:
    df = _current()
    df["Weight"] = 1.0
    set_table(df)


def _clear() -> None:
    set_table(pd.DataFrame(columns=COLUMNS))


def parse_pairs(df: pd.DataFrame) -> tuple[list[PairSpec], list[str]]:
    """Turn editor rows into PairSpecs. Return (pairs, problems to show the user)."""
    pairs: list[PairSpec] = []
    problems: list[str] = []
    for i, r in df.reset_index(drop=True).iterrows():
        long = str(r["Long"] or "").strip().upper() if pd.notna(r["Long"]) else ""
        short = str(r["Short"] or "").strip().upper() if pd.notna(r["Short"]) else ""
        if not long and not short:
            continue  # blank row the user just added
        row = f"Row {i + 1}"
        if not long or not short:
            problems.append(f"{row}: needs both a long and a short ticker.")
            continue
        if long == short:
            problems.append(f"{row}: long and short are both {long}.")
            continue
        w = r["Weight"]
        weight = 1.0 if w is None or (isinstance(w, float) and math.isnan(w)) else float(w)
        if weight < 0:
            problems.append(f"{row}: weight cannot be negative.")
            continue
        sizing = SIZING_LABELS.get(r["Sizing"], SizingMethod.DOLLAR_NEUTRAL)
        pairs.append(PairSpec(long, short, weight, sizing))
    if pairs and sum(p.weight for p in pairs) == 0:
        problems.append("All weights are zero.")
        pairs = []
    return pairs, problems


def render_pair_editor() -> tuple[list[PairSpec], list[str]]:
    _init_state()
    ss = st.session_state

    c1, c2, c3, c4 = st.columns([3, 1, 1, 1], vertical_alignment="bottom")
    c1.selectbox(
        "Add a preset pair", [ALL_PRESETS] + [p.label for p in PRESETS], key="preset_choice",
        help="Classic same-industry pairs. Each one has a short rationale in the Diagnostics tab.",
    )
    c2.button("Add", on_click=_add_preset, width="stretch")
    c3.button("Equal weight", on_click=_equal_weight, width="stretch",
              help="Set every pair's weight to 1 so each gets the same share of gross.")
    c4.button("Clear all", on_click=_clear, width="stretch")

    edited = st.data_editor(
        ss.pairs_df,
        key=f"pairs_editor_{ss.editor_ver}",
        num_rows="dynamic",
        width="stretch",
        hide_index=True,
        column_config={
            "Long": st.column_config.TextColumn("Long (buy)", help="Ticker you buy.", required=True),
            "Short": st.column_config.TextColumn("Short (sell)", help="Ticker you sell short.", required=True),
            "Weight": st.column_config.NumberColumn(
                "Weight", min_value=0.0, step=0.5, default=1.0, format="%.2f",
                help="Relative share of the pair book's gross exposure. Weights are rescaled to sum to 100%.",
            ),
            "Sizing": st.column_config.SelectboxColumn(
                "Sizing method", options=list(SIZING_LABELS), default=SizingMethod.DOLLAR_NEUTRAL.label,
                required=True, help=tip("dollar_vs_beta"),
            ),
        },
    )
    ss.pairs_current = edited
    pairs, problems = parse_pairs(edited)

    if pairs:
        st.caption("**Flip direction** to swap the long and short legs. A quick way to see why direction matters:")
        per_row = 4
        valid_rows = [i for i, r in edited.reset_index(drop=True).iterrows()
                      if pd.notna(r["Long"]) and pd.notna(r["Short"]) and str(r["Long"]).strip() and str(r["Short"]).strip()]
        for start in range(0, len(valid_rows), per_row):
            cols = st.columns(per_row)
            for col, i in zip(cols, valid_rows[start:start + per_row]):
                r = edited.reset_index(drop=True).loc[i]
                col.button(
                    f"⇄  {str(r['Long']).upper()} / {str(r['Short']).upper()}",
                    key=f"flip_{ss.editor_ver}_{i}", on_click=_flip, args=(i,),
                    width="stretch",
                )
        total = sum(p.weight for p in pairs)
        alloc = " · ".join(f"{p.label}: {p.weight / total:.0%}" for p in pairs)
        st.caption(f"Share of gross: {alloc}")
    return pairs, problems
