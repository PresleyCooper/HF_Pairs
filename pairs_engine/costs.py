"""Trading and financing costs.

Accruals use an actual/365 day count: interest and borrow fees accrue on
calendar days, so holding a position over a weekend costs three days of
borrow, as it does at a real prime broker.
"""

from __future__ import annotations

DAYS_PER_YEAR = 365.0


def transaction_cost(traded_notional: float, bps: float) -> float:
    """Cost of trading ``traded_notional`` dollars (either direction) at ``bps``.

    This covers commissions, half the bid/ask spread, and market impact,
    rolled into one number.
    """
    return abs(traded_notional) * bps / 10_000.0


def borrow_fee(short_notional: float, annual_rate: float, days: float) -> float:
    """Fee paid to the stock lender for holding ``short_notional`` for ``days``."""
    return abs(short_notional) * annual_rate * days / DAYS_PER_YEAR


def cash_interest(cash: float, annual_rate: float, days: float) -> float:
    """Interest earned on a cash balance (negative when ``cash`` is borrowed).

    A short sale leaves the sale proceeds with the broker, and those proceeds
    earn interest. So in this simple model cash = NAV - long value + short
    proceeds. One rate is used for lending and borrowing to keep the model
    simple; real funds pay a spread on debit balances.
    """
    return cash * annual_rate * days / DAYS_PER_YEAR
