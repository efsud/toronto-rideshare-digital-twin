"""Rider demand generation."""

from toronto_rideshare.demand.generator import generate_trips
from toronto_rideshare.demand.models import TripRequest

__all__ = ["TripRequest", "generate_trips"]
