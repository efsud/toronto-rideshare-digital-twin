"""Rule-based rider price adjustments by zone imbalance."""

from __future__ import annotations


def rider_adjustment_cad(imbalance: float, *, gain: float = 0.5, cap: float = 5.0) -> float:
    """Positive imbalance (demand > supply) -> premium; negative -> discount."""
    adjustment = gain * imbalance
    return max(-cap, min(cap, adjustment))
