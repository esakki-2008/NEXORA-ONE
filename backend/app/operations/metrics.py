"""Deterministic metric helpers for simulator and connected incident data."""

from __future__ import annotations

import math
from collections.abc import Iterable

from backend.app.simulator.models import SupportSnapshot, TransactionSnapshot


def safe_ratio(numerator: int | float, denominator: int | float) -> float | None:
    """Return a bounded ratio, or no metric when its denominator is absent."""

    if denominator <= 0:
        return None
    value = float(numerator) / float(denominator)
    if not math.isfinite(value):
        return None
    return max(0.0, min(1.0, value))


def transaction_currency(transactions: Iterable[TransactionSnapshot]) -> str | None:
    """Return a currency only when the source is internally consistent."""

    currencies = {item.currency for item in transactions}
    return currencies.pop() if len(currencies) == 1 else None


def transaction_totals(
    transactions: list[TransactionSnapshot],
) -> tuple[int, int, int, float, str | None]:
    """Calculate counts and failed amount without inventing a conversion."""

    succeeded = sum(item.status == "succeeded" for item in transactions)
    failed = sum(item.status == "failed" for item in transactions)
    failed_amount = sum(item.amount for item in transactions if item.status == "failed")
    return len(transactions), succeeded, failed, failed_amount, transaction_currency(transactions)


def support_rate(snapshot: SupportSnapshot, field: str) -> float:
    """Read a known support ratio by name for stable metric construction."""

    values = {
        "escalation_rate": snapshot.escalation_rate,
        "sentiment_signal": snapshot.sentiment_signal,
    }
    return values[field]


__all__ = [
    "safe_ratio",
    "support_rate",
    "transaction_currency",
    "transaction_totals",
]
