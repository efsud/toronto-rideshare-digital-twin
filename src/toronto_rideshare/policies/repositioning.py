"""Capacity-reserving deterministic repositioning."""

from __future__ import annotations

from toronto_rideshare.supply.models import DriverStatus


def suggest_reposition_targets(drivers, zone_imbalance, *, top_k=3, travel_cost=None):
    shortages = sorted(
        (
            (zone, int(stats["imbalance"]))
            for zone, stats in zone_imbalance.items()
            if stats["imbalance"] > 0
        ),
        key=lambda row: (-row[1], row[0]),
    )[:top_k]
    surplus = {zone: max(0, int(-stats["imbalance"])) for zone, stats in zone_imbalance.items()}
    assigned = {}
    for target, capacity in shortages:
        candidates = []
        for driver in drivers:
            if driver.status != DriverStatus.IDLE or driver.driver_id in assigned:
                continue
            if surplus.get(driver.zone, 0) <= 0:
                continue
            cost = travel_cost(driver, target) if travel_cost else 0.0
            if cost is not None:
                candidates.append((cost, driver.driver_id, driver))
        for _, driver_id, driver in sorted(candidates):
            if capacity <= 0:
                break
            if surplus.get(driver.zone, 0) <= 0:
                continue
            assigned[driver_id] = target
            surplus[driver.zone] -= 1
            capacity -= 1
    return assigned
