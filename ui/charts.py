"""Plotly figure builders with one consistent light theme.

Color roles are fixed across the app, so a series is the same color on every
chart:

* the chosen-beta portfolio is blue,
* the market-neutral comparison is orange,
* the benchmark is a neutral gray reference,
* individual pairs take categorical slots in a fixed order.
"""

from __future__ import annotations

from typing import Callable, Iterable

import pandas as pd
import plotly.graph_objects as go

# Validated categorical palette (light mode), in fixed slot order.
CATEGORICAL = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"]
PORTFOLIO = CATEGORICAL[0]
NEUTRAL = CATEGORICAL[1]
BENCH = "#8a8984"
REFERENCE = "#52514e"
GAIN = "#2a78d6"
LOSS = "#e34948"
TEXT = "#0b0b0b"
TEXT_2 = "#52514e"
GRID = "#ebeae6"
SURFACE = "#ffffff"


def _base_layout(fig: go.Figure, title: str | None, yfmt: str | None, height: int) -> go.Figure:
    fig.update_layout(
        title=dict(text=title, x=0, xanchor="left", font=dict(size=15, color=TEXT)) if title else None,
        height=height,
        margin=dict(l=8, r=8, t=56 if title else 24, b=8),
        paper_bgcolor=SURFACE,
        plot_bgcolor=SURFACE,
        font=dict(family="Inter, Segoe UI, Helvetica, Arial, sans-serif", size=12, color=TEXT_2),
        hovermode="x unified",
        hoverlabel=dict(bgcolor="#ffffff", bordercolor=GRID, font=dict(color=TEXT)),
        legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="left", x=0,
                    font=dict(color=TEXT_2), bgcolor="rgba(0,0,0,0)"),
    )
    fig.update_xaxes(showgrid=False, linecolor=GRID, tickcolor=GRID, ticks="outside",
                     showspikes=True, spikemode="across", spikecolor="#c3c2b7",
                     spikethickness=1, spikedash="solid")
    fig.update_yaxes(gridcolor=GRID, zeroline=True, zerolinecolor="#d6d5d0", zerolinewidth=1,
                     tickformat=yfmt, linecolor=GRID)
    return fig


def line_chart(
    series: Iterable[tuple[str, pd.Series, str, str]],
    title: str | None = None,
    yfmt: str | None = None,
    height: int = 380,
    hline: tuple[float, str] | None = None,
) -> go.Figure:
    """Lines from ``(name, series, color, dash)`` tuples. ``hline`` = (y, label)."""
    fig = go.Figure()
    hover_fmt = yfmt or ",.2f"
    for name, s, color, dash in series:
        fig.add_trace(go.Scatter(
            x=s.index, y=s.values, name=name, mode="lines",
            line=dict(color=color, width=2, dash=dash),
            hovertemplate=f"%{{y:{hover_fmt}}}<extra>{name}</extra>",
        ))
    if hline is not None:
        y, label = hline
        fig.add_hline(y=y, line=dict(color=REFERENCE, width=1.5, dash="dash"),
                      annotation_text=label, annotation_position="top left",
                      annotation_font=dict(color=TEXT_2, size=11))
    return _base_layout(fig, title, yfmt, height)


def equity_chart(curves: list[tuple[str, pd.Series, str, str]], title: str, height: int = 420) -> go.Figure:
    fig = line_chart(curves, title=title, yfmt="$,.0f", height=height)
    return fig


def drawdown_chart(curves: list[tuple[str, pd.Series, str, str]], title: str = "Drawdown from peak") -> go.Figure:
    fig = line_chart(curves, title=title, yfmt=".0%", height=320)
    # Light fill under the primary series so the depth of each drawdown is visible.
    if fig.data:
        fig.data[0].update(fill="tozeroy", fillcolor="rgba(42,120,214,0.12)")
    return fig


def pair_lines(df: pd.DataFrame, title: str, yfmt: str = ".2f", height: int = 400) -> go.Figure:
    """One line per pair using categorical slots in column order."""
    series = [(c, df[c], CATEGORICAL[i % len(CATEGORICAL)], "solid") for i, c in enumerate(df.columns)]
    return line_chart(series, title=title, yfmt=yfmt, height=height)


def money(x: float) -> str:
    return f"-${abs(x):,.0f}" if x < 0 else f"${x:,.0f}"


def bar_chart(
    values: pd.Series,
    title: str,
    xfmt: str = "$,.0f",
    label: Callable[[float], str] = money,
    height: int | None = None,
) -> go.Figure:
    """Horizontal bars, colored by sign (gain blue / loss red), labelled with values."""
    v = values.sort_values()
    colors = [GAIN if x >= 0 else LOSS for x in v.values]
    fig = go.Figure(go.Bar(
        x=v.values, y=v.index, orientation="h", marker=dict(color=colors, line=dict(width=0)),
        text=[label(x) for x in v.values],
        textposition="outside", textfont=dict(color=TEXT_2, size=11), cliponaxis=False,
        hovertemplate=f"%{{y}}: %{{x:{xfmt}}}<extra></extra>",
    ))
    fig = _base_layout(fig, title, None, height or max(220, 44 * len(v) + 80))
    fig.update_layout(hovermode="closest", bargap=0.35, showlegend=False)
    fig.update_xaxes(tickformat=xfmt, showgrid=True, gridcolor=GRID, showspikes=False,
                     zeroline=True, zerolinecolor=REFERENCE)
    fig.update_yaxes(showgrid=False, tickfont=dict(color=TEXT))
    return fig
