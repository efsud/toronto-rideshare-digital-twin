"""Rule-based driver bonuses by zone imbalance."""

from __future__ import annotations


def driver_bonus_cad(imbalance: float, *, gain: float = 1.0, cap: float = 12.0) -> float:
    """Undersupplied zones (imbalance > 0) receive non-negative bonuses."""
    bonus = gain * max(0.0, imbalance)
    return min(cap, bonus)
