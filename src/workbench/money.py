"""Exact money arithmetic. Every rounding step is explicit half up (START_HERE · MONEY).

Python's Decimal defaults to banker's rounding and DuckDB DECIMAL division returns DOUBLE, so any
calculation that divides (e.g. day/365 recognition) goes through these helpers, never raw SQL.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")


def round_cents(x: Decimal) -> Decimal:
    return x.quantize(CENT, rounding=ROUND_HALF_UP)


def round_whole(x: Decimal) -> int:
    return int(x.quantize(Decimal(1), rounding=ROUND_HALF_UP))


def cents_to_usd(cents: int | str) -> Decimal:
    """Stripe integer cents -> USD, exactly."""
    return Decimal(int(cents)) * CENT


def day_share(amount: Decimal, days: int, basis: int = 365) -> Decimal:
    """amount x days / basis, rounded once to cents half up (START_HERE · ACCOUNTING: actual days / 365)."""
    return round_cents(Decimal(amount) * days / basis)
