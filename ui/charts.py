"""Plotly figure builders with one consistent light theme.

Color roles are fixed across the app, so a series is the same color on every
chart:

* the chosen-beta portfolio is blue,
* the market-neutral comparison is orange,
* the benchmark is a neutral gray reference,
* individual pairs take categorical slots in a fixed order.

Layout rules that keep text from overlapping:

* Chart titles are drawn by Streamlit above the figure (see ``show``), never
  inside the Plotly canvas, so a legend that wraps can't collide with them.
* Legends sit above the plot area. Plotly grows the top margin to fit them.
* Reference lines (target beta, zero, "your setting") are legend entries,
  not floating annotations that can land on top of the data.
* Bar charts pad their value axis so outside labels always have room.
"""

from __future__ import annotations

from typing import Callable, Iterable

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

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


PLOT_CONFIG = {"displaylogo": False}


def show(fig: go.Figure, where=st) -> None:
    """Render a figure with its title as Streamlit text above it.

    ``where`` is any Streamlit container (``st``, a column, an expander).
    """
    title = (fig.layout.meta or {}).get("title") if isinstance(fig.layout.meta, dict) else None
    if title:
        where.markdown(f"**{title.replace('$', chr(92) + '$')}**")
    where.plotly_chart(fig, width="stretch", config=PLOT_CONFIG)


def _base_layout(fig: go.Figure, title: str | None, yfmt: str | None, height: int) -> go.Figure:
    fig.update_layout(
        meta={"title": title},
        height=height,
        margin=dict(l=8, r=8, t=8, b=8, autoexpand=True),
        paper_bgcolor=SURFACE,
        plot_bgcolor=SURFACE,
        font=dict(family="Inter, Segoe UI, Helvetica, Arial, sans-serif", size=12, color=TEXT_2),
        hovermode="x unified",
        hoverlabel=dict(bgcolor="#ffffff", bordercolor=GRID, font=dict(color=TEXT)),
        legend=dict(orientation="h", yanchor="bottom", y=1.05, xanchor="left", x=0,
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
        add_reference_line(fig, *hline)
    return _base_layout(fig, title, yfmt, height)


def add_reference_line(fig: go.Figure, y: float, label: str) -> None:
    """A dashed horizontal reference line that appears in the legend."""
    xs = [x for tr in fig.data for x in (tr.x if tr.x is not None else [])]
    if not xs:
        return
    fig.add_trace(go.Scatter(
        x=[min(xs), max(xs)], y=[y, y], mode="lines", name=label,
        line=dict(color=REFERENCE, width=1.5, dash="dash"), hoverinfo="skip",
    ))


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


def band_chart(
    value: pd.Series,
    mean: pd.Series,
    std: pd.Series,
    name: str,
    title: str,
    height: int = 400,
) -> go.Figure:
    """A series with its trailing mean and shaded ±1σ / ±2σ bands."""
    fig = go.Figure()
    for k, alpha in ((2, 0.08), (1, 0.14)):
        upper, lower = mean + k * std, mean - k * std
        fig.add_trace(go.Scatter(x=upper.index, y=upper.values, mode="lines", line=dict(width=0),
                                 showlegend=False, hoverinfo="skip"))
        fig.add_trace(go.Scatter(
            x=lower.index, y=lower.values, mode="lines", line=dict(width=0), fill="tonexty",
            fillcolor=f"rgba(42,120,214,{alpha})", name=f"±{k}σ band", hoverinfo="skip",
        ))
    fig.add_trace(go.Scatter(x=mean.index, y=mean.values, mode="lines", name="Trailing mean",
                             line=dict(color=REFERENCE, width=1.5, dash="dash"),
                             hovertemplate="%{y:.3f}<extra>Trailing mean</extra>"))
    fig.add_trace(go.Scatter(x=value.index, y=value.values, mode="lines", name=name,
                             line=dict(color=PORTFOLIO, width=2),
                             hovertemplate=f"%{{y:.3f}}<extra>{name}</extra>"))
    return _base_layout(fig, title, ".2f", height)


def money(x: float) -> str:
    return f"-${abs(x):,.0f}" if x < 0 else f"${x:,.0f}"


def bar_chart(
    values: pd.Series,
    title: str,
    xfmt: str = "$,.0f",
    label: Callable[[float], str] = money,
    height: int | None = None,
    sort: bool = True,
) -> go.Figure:
    """Horizontal bars, colored by sign (gain blue / loss red), labelled with values.

    Unsorted bars keep the series order top to bottom.
    """
    v = values.sort_values() if sort else values.iloc[::-1]
    colors = [GAIN if x >= 0 else LOSS for x in v.values]
    fig = go.Figure(go.Bar(
        x=v.values, y=v.index, orientation="h", marker=dict(color=colors, line=dict(width=0)),
        text=[label(x) for x in v.values],
        textposition="outside", textfont=dict(color=TEXT_2, size=11), cliponaxis=False,
        hovertemplate=f"%{{y}}: %{{x:{xfmt}}}<extra></extra>",
    ))
    fig = _base_layout(fig, title, None, height or max(220, 44 * len(v) + 80))
    fig.update_layout(hovermode="closest", bargap=0.35, showlegend=False)
    lo, hi = min(float(v.min()), 0.0), max(float(v.max()), 0.0)
    pad = 0.22 * (hi - lo or 1.0)
    fig.update_xaxes(tickformat=xfmt, showgrid=True, gridcolor=GRID, showspikes=False,
                     zeroline=True, zerolinecolor=REFERENCE,
                     range=[lo - (pad if lo < 0 else 0), hi + (pad if hi > 0 else 0)])
    fig.update_yaxes(showgrid=False, tickfont=dict(color=TEXT))
    return fig


def grouped_bar(df: pd.DataFrame, colors: list[str], title: str, yfmt: str = ".0%", height: int = 380,
                textfmt: str = ".1%") -> go.Figure:
    """Vertical grouped bars: one group per row, one bar per column."""
    fig = go.Figure()
    for col, color in zip(df.columns, colors):
        fig.add_trace(go.Bar(
            x=df.index, y=df[col], name=col, marker=dict(color=color, line=dict(width=0)),
            text=[f"{v:{textfmt}}" if pd.notna(v) else "n/a" for v in df[col]],
            textposition="outside", textfont=dict(size=11, color=TEXT_2), cliponaxis=False,
            hovertemplate=f"%{{x}}<br>{col}: %{{y:{yfmt}}}<extra></extra>",
        ))
    fig = _base_layout(fig, title, yfmt, height)
    fig.update_layout(barmode="group", bargap=0.3, bargroupgap=0.08, hovermode="closest")
    fig.update_xaxes(showspikes=False, ticks="")
    # Pad the value axis so the outside labels on the tallest bars have room.
    vals = df.to_numpy(dtype=float)
    vals = vals[~pd.isna(vals)]
    if vals.size:
        lo, hi = min(vals.min(), 0.0), max(vals.max(), 0.0)
        pad = 0.15 * (hi - lo or 1.0)
        fig.update_yaxes(range=[lo - (pad if lo < 0 else 0), hi + (pad if hi > 0 else 0)])
    return fig


def sweep_chart(x: pd.Index, y: pd.Series, current: float, title: str, yfmt: str, height: int = 320,
                color: str = PORTFOLIO) -> go.Figure:
    """A metric across target betas, with the slider's current value marked."""
    fig = go.Figure(go.Scatter(
        x=list(x), y=y.values, mode="lines+markers", line=dict(color=color, width=2),
        marker=dict(size=8, color=color, line=dict(color=SURFACE, width=2)), name=y.name,
        hovertemplate=f"Target β %{{x:+.1f}}: %{{y:{yfmt}}}<extra></extra>",
    ))
    lo, hi = float(y.min()), float(y.max())
    fig.add_trace(go.Scatter(
        x=[current, current], y=[lo, hi], mode="lines", name=f"Your setting (β {current:+.2f})",
        line=dict(color=REFERENCE, width=1.5, dash="dash"), hoverinfo="skip",
    ))
    fig.data[0].showlegend = False
    fig = _base_layout(fig, title, yfmt, height)
    fig.update_layout(hovermode="closest")
    fig.update_xaxes(title=dict(text="Target beta", font=dict(color=TEXT_2)), showspikes=False,
                     tickformat="+.1f", dtick=0.25)
    return fig
