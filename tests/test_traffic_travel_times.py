from __future__ import annotations

import math

import pytest

from toronto_rideshare.traffic.travel_times import compute_tau_e


def test_compute_tau_e_doubles_when_speed_halves() -> None:
    travel_time_s, congestion_ratio = compute_tau_e(
        edge_length_m=1000.0,
        observed_speed_kph=25.0,
        free_flow_speed_kph=50.0,
        free_flow_travel_time_s=72.0,
    )

    assert math.isclose(travel_time_s, 144.0)
    assert math.isclose(congestion_ratio, 2.0)


def test_compute_tau_e_rejects_non_positive_speed() -> None:
    with pytest.raises(ValueError, match="positive"):
        compute_tau_e(
            edge_length_m=1000.0,
            observed_speed_kph=0.0,
        )
