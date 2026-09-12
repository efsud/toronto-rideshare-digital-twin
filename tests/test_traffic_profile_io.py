from __future__ import annotations

import pandas as pd
import pytest

from toronto_rideshare.traffic.models import TrafficProfile
from toronto_rideshare.traffic.travel_times import load_traffic_profile, save_traffic_profile

pytest.importorskip("pyarrow")


def make_profile() -> TrafficProfile:
    frame = pd.DataFrame(
        {
            "u": [1],
            "v": [2],
            "key": [0],
            "time_bucket": ["08:30"],
            "observed_speed_kph": [25.0],
            "free_flow_speed_kph": [50.0],
            "travel_time_s": [144.0],
            "congestion_ratio": [2.0],
            "n_observations": [1],
        }
    )
    return TrafficProfile(edge_stats=frame)


def test_traffic_profile_save_and_load_round_trip(tmp_path) -> None:
    profile = make_profile()
    path = tmp_path / "edge_traffic_profile.parquet"

    save_traffic_profile(profile, path)
    loaded = load_traffic_profile(path)

    assert loaded.edge_stats.equals(profile.edge_stats)
    assert loaded.lookup_travel_time_s(1, 2, 0, "08:30") == 144.0
