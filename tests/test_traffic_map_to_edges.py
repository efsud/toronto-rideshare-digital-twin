from __future__ import annotations

import geopandas as gpd
import pandas as pd
from shapely.geometry import LineString, Point

from toronto_rideshare.traffic.map_to_edges import (
    aggregate_edge_speeds,
    map_observations_to_edges,
)


def make_test_edges() -> gpd.GeoDataFrame:
    line = LineString([(-79.4000, 43.6500), (-79.3900, 43.6500)])
    return gpd.GeoDataFrame(
        {"u": [1], "v": [2], "key": [0], "highway": ["primary"], "geometry": [line]},
        crs="EPSG:4326",
    )


def make_test_observations() -> gpd.GeoDataFrame:
    point = Point(-79.3950, 43.6500)
    frame = pd.DataFrame(
        {
            "observation_id": ["OBS_1"],
            "latitude": [43.6500],
            "longitude": [-79.3950],
            "datetime": [pd.Timestamp("2024-03-15T08:30:00", tz="UTC")],
            "speed_kph": [30.0],
            "time_bucket": ["08:30"],
        }
    )
    return gpd.GeoDataFrame(frame, geometry=[point], crs="EPSG:4326")


def test_map_observations_to_nearest_edge() -> None:
    mapping = map_observations_to_edges(make_test_observations(), make_test_edges())

    assert len(mapping) == 1
    assert mapping.iloc[0]["u"] == 1
    assert mapping.iloc[0]["v"] == 2
    assert mapping.iloc[0]["key"] == 0
    assert mapping.iloc[0]["match_distance_m"] <= 50.0


def test_aggregate_edge_speeds_by_time_bucket() -> None:
    mapping = map_observations_to_edges(make_test_observations(), make_test_edges())
    aggregated = aggregate_edge_speeds(mapping, make_test_observations())

    assert aggregated.iloc[0]["observed_speed_kph"] == 30.0
    assert aggregated.iloc[0]["time_bucket"] == "08:30"
    assert aggregated.iloc[0]["n_observations"] == 1
