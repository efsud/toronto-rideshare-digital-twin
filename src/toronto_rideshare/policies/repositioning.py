"""Simple driver repositioning toward undersupplied zones."""

from __future__ import annotations

from toronto_rideshare.supply.models import Driver, DriverStatus
from toronto_rideshare.zones import zone_center


def suggest_reposition_targets(
    drivers: list[Driver],
    zone_imbalance: dict[str, dict[str, float]],
    *,
    top_k: int = 3,
) -> dict[str, str]:
    """Assign idle drivers in oversupplied zones to most undersupplied zones."""
    undersupplied = sorted(
        zone_imbalance.items(),
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
            lat, lon = zone_center(target_zone)
            driver.lat, driver.lon = lat, lon
            driver.zone = target_zone
            driver.status = DriverStatus.REPOSITIONING
    return assignments
