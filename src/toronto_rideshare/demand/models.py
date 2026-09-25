"""Demand-side data models."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TripRequest:
    """One rider trip request."""

    request_id: str
    request_time_min: float
    origin_lat: float
    origin_lon: float
    destination_lat: float
    destination_lon: float
    origin_zone: str
    destination_zone: str
