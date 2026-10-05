"""The daily simulation loop.

Timing convention (this is what guarantees no lookahead)
--------------------------------------------------------
Everything happens at the close of each trading day ``t``:

1. Positions held since the close of ``t-1`` earn the return from ``t-1`` to
   ``t``. Interest and borrow accrue over the calendar days in between.
2. If ``t`` is a rebalance date, new target positions are computed using
   betas and vols estimated from returns *up to and including* ``t``, and
   trades are made at ``t``'s closing price, paying transaction costs.
3. Those positions then earn the return from ``t`` to ``t+1`` on the next
   loop iteration.

So a decision never uses a return it hasn't "seen" yet.

Book structure
--------------
The portfolio is a set of *slots*: a long slot and a short slot per pair,
plus one benchmark overlay slot. Each slot holds a signed dollar market value
(positive long, negative short) that drifts with its own returns between
rebalances, exactly as a fixed number of shares would. Trades are not netted
across pairs, even if two pairs share a ticker, which keeps attribution clean.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .beta import rolling_beta, rolling_vol
from .config import BacktestConfig, PairSpec, RebalanceFreq
from .costs import DAYS_PER_YEAR
from .data import PairAvailability, PriceData, check_pair_history
from .sizing import size_pair

OVERLAY = "Beta overlay"


@dataclass
class BacktestResult:
    """Everything the analytics and UI layers need from one run.

    All DataFrames are indexed by trading date. Per-slot frames have one
    column per slot (see ``slots`` for each slot's pair, leg and ticker).
    """

    config: BacktestConfig
    pairs: list[PairSpec]  # pairs that actually traded, in book order
    pair_names: list[str]  # unique display names, aligned with ``pairs``
    nav: pd.Series
    returns: pd.Series
    bench_returns: pd.Series
    positions: pd.DataFrame  # signed market value per slot after trading
    market_pnl: pd.DataFrame  # price/dividend P&L per slot
    trading_costs: pd.DataFrame  # transaction costs per slot (positive = cost)
    borrow_costs: pd.DataFrame  # borrow fees per slot (positive = cost)
    interest: pd.Series  # interest on cash (positive = earned)
    book_beta: pd.Series  # ex-ante beta of the pair book alone
    total_beta: pd.Series  # ex-ante beta including the overlay
    slots: pd.DataFrame  # columns: slot, pair, leg, ticker
    rebalance_dates: pd.DatetimeIndex
    availability: list[PairAvailability]
    sizing_notes: dict[str, dict[str, int]] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    @property
    def net_pnl(self) -> pd.DataFrame:
        """Per-slot P&L after trading and borrow costs (excludes cash interest)."""
        return self.market_pnl - self.trading_costs - self.borrow_costs

    def pair_pnl(self) -> pd.DataFrame:
        """Daily net P&L per pair (and the overlay), in dollars."""
        by = self.slots.set_index("slot")["pair"]
        return self.net_pnl.T.groupby(by).sum().T[self.pair_names + [OVERLAY]]

    def leg_pnl(self) -> pd.DataFrame:
        """Daily net P&L summed by leg: long, short, overlay."""
        by = self.slots.set_index("slot")["leg"]
        return self.net_pnl.T.groupby(by).sum().T.reindex(columns=["long", "short", "overlay"])


def _unique_names(pairs: list[PairSpec]) -> list[str]:
    seen: dict[str, int] = {}
    names = []
    for p in pairs:
        n = seen.get(p.label, 0) + 1
        seen[p.label] = n
        names.append(p.label if n == 1 else f"{p.label} ({n})")
    return names


def _rebalance_flags(dates: pd.DatetimeIndex, freq: RebalanceFreq) -> np.ndarray:
    """True on day 0 and on the first trading day of each new period."""
    flags = np.zeros(len(dates), dtype=bool)
    flags[0] = True
    if freq is RebalanceFreq.DAILY:
        flags[:] = True
    elif freq in (RebalanceFreq.WEEKLY, RebalanceFreq.MONTHLY):
        period = dates.to_period("W" if freq is RebalanceFreq.WEEKLY else "M")
        flags[1:] = period[1:] != period[:-1]
    return flags


def run_backtest(pairs: list[PairSpec], config: BacktestConfig, data: PriceData) -> BacktestResult:
    """Simulate the pair book plus beta overlay over ``config``'s date range.

    ``data`` must contain every pair ticker plus the benchmark, and should
    start early enough to warm up the rolling beta window (see
    ``data.warmup_start``). Pairs without enough history are skipped and
    reported in ``availability``.
    """
    bench = config.benchmark
    if bench not in data.tickers:
        raise ValueError(f"Benchmark {bench} is missing from the price data")

    warnings: list[str] = []
    availability = check_pair_history(pairs, data, config.start, config.end, config.beta_window)
    live = [a for a in availability if a.usable and a.pair.weight > 0]
    for a in availability:
        for w in a.warnings:
            warnings.append(f"{a.pair.label}: {w}")
    live_pairs = [a.pair for a in live]
    names = _unique_names(live_pairs)

    # ---- Point-in-time estimates on the full (warm-up inclusive) history ----
    tot_ret = data.total_returns()
    px_ret = data.price_returns()
    stock_tickers = sorted({t for p in live_pairs for t in (p.long, p.short)})
    betas = rolling_beta(tot_ret[stock_tickers], tot_ret[bench], config.beta_window)
    vols = rolling_vol(tot_ret[stock_tickers], config.beta_window)

    idx = data.index
    in_window = (idx >= pd.Timestamp(config.start)) & (idx <= pd.Timestamp(config.end))
    dates = idx[in_window]
    if len(dates) < 2:
        raise ValueError("Fewer than two trading days in the selected date range")
    T = len(dates)

    # ---- Slot layout: [p0 long, p0 short, p1 long, p1 short, ..., overlay] ----
    slot_rows = []
    for name, p in zip(names, live_pairs):
        slot_rows.append((f"{name} | long {p.long}", name, "long", p.long))
        slot_rows.append((f"{name} | short {p.short}", name, "short", p.short))
    slot_rows.append((f"{OVERLAY} | {bench}", OVERLAY, "overlay", bench))
    slots = pd.DataFrame(slot_rows, columns=["slot", "pair", "leg", "ticker"])
    S = len(slots)
    slot_tickers = slots["ticker"].tolist()

    # Returns earned by a long holder (total) and paid by a short holder.
    r_long = tot_ret.loc[dates, slot_tickers].to_numpy(dtype=float)
    r_short_src = tot_ret if config.charge_short_dividends else px_ret
    r_short = r_short_src.loc[dates, slot_tickers].to_numpy(dtype=float)
    r_long = np.nan_to_num(r_long)
    r_short = np.nan_to_num(r_short)

    beta_mat = np.ones((T, S))  # overlay column stays 1.0: the benchmark's own beta
    vol_mat = np.full((T, S), np.nan)
    for j, tk in enumerate(slot_tickers[:-1]):
        beta_mat[:, j] = betas.loc[dates, tk].to_numpy()
        vol_mat[:, j] = vols.loc[dates, tk].to_numpy()
    beta_for_risk = np.nan_to_num(beta_mat)

    ready = np.zeros((T, len(live_pairs)), dtype=bool)
    for k, a in enumerate(live):
        ready[:, k] = dates >= a.first_tradable
    weights = np.array([p.weight for p in live_pairs], dtype=float)

    borrow_rates = np.array([config.etf_borrow_rate if leg == "overlay" else config.borrow_rate
                                for leg in slots["leg"]])
    day_gaps = np.zeros(T)
    day_gaps[1:] = (dates[1:] - dates[:-1]).days
    rebal = _rebalance_flags(dates, config.rebalance)
    if config.rebalance is RebalanceFreq.NEVER and not ready[0].all() and len(live_pairs):
        late = [names[k] for k in range(len(live_pairs)) if not ready[0, k]]
        warnings.append(
            "Rebalance is 'never', so pairs not tradable on day one are never added: "
            + ", ".join(late)
        )

    # ---- Output buffers ----
    pos_out = np.zeros((T, S))
    pnl_out = np.zeros((T, S))
    tc_out = np.zeros((T, S))
    borrow_out = np.zeros((T, S))
    int_out = np.zeros(T)
    nav_out = np.zeros(T)
    book_beta_out = np.zeros(T)
    total_beta_out = np.zeros(T)
    notes = {n: {"floored": 0, "fallback": 0} for n in names}

    v = np.zeros(S)  # signed market value per slot
    nav = float(config.initial_capital)
    wiped_out = False

    for t in range(T):
        # 1) Accrue: market moves, borrow fees and cash interest since t-1.
        if t > 0:
            dt = day_gaps[t]
            cash = nav - v.sum()
            interest = cash * config.cash_rate * dt / DAYS_PER_YEAR
            borrow = np.where(v < 0, -v * borrow_rates * dt / DAYS_PER_YEAR, 0.0)
            r = np.where(v >= 0, r_long[t], r_short[t])
            pnl = v * r
            v = v * (1.0 + r)
            nav = nav + pnl.sum() + interest - borrow.sum()
            pnl_out[t], borrow_out[t], int_out[t] = pnl, borrow, interest

        if nav <= 0:
            wiped_out = True
            warnings.append(f"Portfolio equity hit zero on {dates[t].date()}; simulation stopped.")
            nav_out[t:] = 0.0
            break

        # 2) Rebalance: size each live pair, then hedge the book to target beta.
        if rebal[t]:
            target = np.zeros(S)
            active = ready[t] & (weights > 0)
            if active.any():
                w = np.where(active, weights, 0.0)
                w = w / w.sum()
                for k in np.flatnonzero(active):
                    lj, sj = 2 * k, 2 * k + 1
                    sizes = size_pair(
                        live_pairs[k].sizing,
                        gross=config.gross_leverage * nav * w[k],
                        beta_long=beta_mat[t, lj], beta_short=beta_mat[t, sj],
                        vol_long=vol_mat[t, lj], vol_short=vol_mat[t, sj],
                        floor=config.sizing_floor,
                    )
                    notes[names[k]]["floored"] += int(sizes.floored)
                    notes[names[k]]["fallback"] += int(sizes.fallback)
                    target[lj], target[sj] = sizes.long, -sizes.short
            book_beta_dollars = float(np.dot(target[:-1], beta_for_risk[t, :-1]))
            # Overlay notional = (target beta - book beta) * NAV, since the
            # benchmark's beta to itself is 1. Outside the gross budget.
            target[-1] = config.target_beta * nav - book_beta_dollars
            trades = target - v
            tc = np.abs(trades) * config.tc_bps / 10_000.0
            nav -= tc.sum()
            tc_out[t] = tc
            v = target

        pos_out[t] = v
        nav_out[t] = nav
        book_beta_out[t] = float(np.dot(v[:-1], beta_for_risk[t, :-1])) / nav
        total_beta_out[t] = book_beta_out[t] + v[-1] / nav

    cols = slots["slot"].tolist()
    frame = lambda a: pd.DataFrame(a, index=dates, columns=cols)  # noqa: E731
    nav_s = pd.Series(nav_out, index=dates, name="NAV")
    prev = nav_s.shift(1)
    prev.iloc[0] = config.initial_capital
    rets = (nav_s / prev - 1.0).rename("Portfolio")
    if wiped_out:
        rets = rets.fillna(0.0).replace([np.inf, -np.inf], 0.0)
    bench_rets = tot_ret.loc[dates, bench].copy()
    bench_rets.iloc[0] = 0.0
    bench_rets.name = bench

    return BacktestResult(
        config=config,
        pairs=live_pairs,
        pair_names=names,
        nav=nav_s,
        returns=rets,
        bench_returns=bench_rets.fillna(0.0),
        positions=frame(pos_out),
        market_pnl=frame(pnl_out),
        trading_costs=frame(tc_out),
        borrow_costs=frame(borrow_out),
        interest=pd.Series(int_out, index=dates, name="Interest"),
        book_beta=pd.Series(book_beta_out, index=dates, name="Book beta"),
        total_beta=pd.Series(total_beta_out, index=dates, name="Total beta"),
        slots=slots,
        rebalance_dates=dates[rebal],
        availability=availability,
        sizing_notes=notes,
        warnings=warnings,
    )
