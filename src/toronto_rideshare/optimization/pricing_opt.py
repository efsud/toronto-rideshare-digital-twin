"""OR-Tools LP stub for zone-level rider/driver adjustments."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PricingDecision:
    zone: str
    rider_adjustment_cad: float
    driver_bonus_cad: float


def optimize_zone_pricing(
    zone_imbalance: dict[str, dict[str, float]],
    *,
    rider_cap: float = 5.0,
    bonus_cap: float = 12.0,
) -> list[PricingDecision]:
    """Heuristic benchmark before full OR-Tools LP (Task 22 extension point)."""
    from toronto_rideshare.policies.incentives import driver_bonus_cad
    from toronto_rideshare.policies.pricing import rider_adjustment_cad

    decisions: list[PricingDecision] = []
    for zone, stats in zone_imbalance.items():
        imb = float(stats["imbalance"])
        decisions.append(
            PricingDecision(
                zone=zone,
                rider_adjustment_cad=rider_adjustment_cad(imb, cap=rider_cap),
                driver_bonus_cad=driver_bonus_cad(imb, cap=bonus_cap),
            )
        )
    return decisions
