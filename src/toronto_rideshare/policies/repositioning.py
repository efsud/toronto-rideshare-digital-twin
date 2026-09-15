"""Simple driver repositioning toward undersupplied zones."""

from __future__ import annotations

from toronto_rideshare.supply.models import Driver, DriverStatus


def suggest_reposition_targets(
    drivers: list[Driver],
    zone_imbalance: dict[str, dict[str, float]],
    *,
    top_k: int = 3,
) -> dict[str, str]:
    """Assign idle drivers in oversupplied zones to most undersupplied zones."""
    undersupplied = sorted(
        (
            item
            for item in zone_imbalance.items()
            if float(item[1]["imbalance"]) > 0.0
        ),
        key=lambda item: item[1]["imbalance"],
        reverse=True,
    )[:top_k]
    if not undersupplied:
        return {}

    target_zone = undersupplied[0][0]
    assignments: dict[str, str] = {}
    for driver in drivers:
        if driver.status != DriverStatus.IDLE:
            continue
        info = zone_imbalance.get(driver.zone, {"imbalance": 0.0})
        if info["imbalance"] < 0:
            assignments[driver.driver_id] = target_zone
    return assignments
