"""Supply-side driver models."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class DriverStatus(StrEnum):
    IDLE = "idle"
    EN_ROUTE_PICKUP = "en_route_pickup"
    WITH_RIDER = "with_rider"
    REPOSITIONING = "repositioning"


@dataclass
class Driver:
    """One driver agent."""

    driver_id: str
    lat: float
    lon: float
    zone: str
    status: DriverStatus = DriverStatus.IDLE
    available_time_min: float = 0.0
