"""Compute time-dependent edge travel times tau_e(t)."""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import networkx as nx
import pandas as pd

from toronto_rideshare.traffic.ingest import clean_observations, load_traffic_observations
from toronto_rideshare.traffic.map_to_edges import (
    aggregate_edge_speeds,
    graph_edges_gdf,
    map_observations_to_edges,
)
from toronto_rideshare.traffic.models import (
    DEFAULT_TIME_BUCKETS,
    PROFILE_COLUMNS,
    TrafficProfile,
)


def compute_tau_e(
    *,
    edge_length_m: float,
    observed_speed_kph: float,
    free_flow_speed_kph: float | None = None,
    free_flow_travel_time_s: float | None = None,
) -> tuple[float, float]:
    """Return travel_time_s and congestion_ratio for one edge and time bucket."""
    if observed_speed_kph <= 0:
        msg = "observed_speed_kph must be positive."
        raise ValueError(msg)

    travel_time_s = edge_length_m / (observed_speed_kph * 1000.0 / 3600.0)

    if free_flow_speed_kph is not None and free_flow_speed_kph > 0:
        congestion_ratio = free_flow_speed_kph / observed_speed_kph
    elif free_flow_travel_time_s is not None and free_flow_travel_time_s > 0:
        congestion_ratio = travel_time_s / free_flow_travel_time_s
    else:
        congestion_ratio = 1.0

    return travel_time_s, congestion_ratio


def _edge_free_flow_speed_kph(data: dict) -> float:
    length_m = float(data["length"])
    travel_time_s = float(data["travel_time"])
    if travel_time_s <= 0:
        return 35.0
    return (length_m / 1000.0) / (travel_time_s / 3600.0)


def _iter_graph_edges(graph: nx.MultiDiGraph) -> list[dict]:
    rows: list[dict] = []
    for u, v, key, data in graph.edges(keys=True, data=True):
        rows.append(
            {
                "u": int(u),
                "v": int(v),
                "key": int(key),
                "length": float(data["length"]),
                "travel_time": float(data["travel_time"]),
                "highway": str(data.get("highway", "unclassified")),
                "free_flow_speed_kph": _edge_free_flow_speed_kph(data),
            }
        )
    return rows


def _fill_missing_speeds(
    edge_rows: pd.DataFrame,
    aggregated: pd.DataFrame,
    time_bucket: str,
) -> pd.DataFrame:
    """Apply highway-type and citywide fallbacks for edges without observations."""
    bucket_agg = aggregated[aggregated["time_bucket"] == time_bucket].copy()
    direct = edge_rows.merge(
        bucket_agg,
        on=["u", "v", "key"],
        how="left",
    )
    direct["time_bucket"] = time_bucket

    highway_medians = (
        direct.dropna(subset=["observed_speed_kph"])
        .groupby("highway", as_index=False)["observed_speed_kph"]
        .median()
        .rename(columns={"observed_speed_kph": "highway_median_speed_kph"})
    )
    direct = direct.merge(highway_medians, on="highway", how="left")

    citywide_median = direct["observed_speed_kph"].median()
    if pd.isna(citywide_median):
        citywide_median = direct["free_flow_speed_kph"].median()

    direct["cost_source"] = "direct_observation"
    direct.loc[direct["observed_speed_kph"].isna(), "cost_source"] = "citywide_imputation"
    direct.loc[
        direct["observed_speed_kph"].isna() & direct["highway_median_speed_kph"].notna(),
        "cost_source",
    ] = "highway_imputation"
    if bucket_agg.empty:
        direct["cost_source"] = "free_flow"
        direct["observed_speed_kph"] = direct["free_flow_speed_kph"]
    direct["observed_speed_kph"] = direct["observed_speed_kph"].fillna(
        direct["highway_median_speed_kph"]
    )
    direct["observed_speed_kph"] = direct["observed_speed_kph"].fillna(citywide_median)
    direct["observed_speed_kph"] = direct["observed_speed_kph"].fillna(
        direct["free_flow_speed_kph"]
    )
    direct["n_observations"] = direct["n_observations"].fillna(0).astype(int)
    return direct


def build_traffic_profile(
    graph: nx.MultiDiGraph,
    observations: gpd.GeoDataFrame,
    *,
    time_buckets: tuple[str, ...] = DEFAULT_TIME_BUCKETS,
    max_distance_m: float = 50.0,
) -> tuple[TrafficProfile, pd.DataFrame]:
    """Build edge-level tau_e(t) from mapped traffic observations."""
    cleaned = clean_observations(observations)
    edges = graph_edges_gdf(graph)
    mapping = map_observations_to_edges(
        cleaned,
        edges,
        max_distance_m=max_distance_m,
    )
    aggregated = aggregate_edge_speeds(mapping, cleaned)

    edge_rows = pd.DataFrame(_iter_graph_edges(graph))
    profile_parts: list[pd.DataFrame] = []

    for bucket in time_buckets:
        filled = _fill_missing_speeds(edge_rows, aggregated, bucket)
        travel_times: list[float] = []
        congestion_ratios: list[float] = []
        for row in filled.itertuples(index=False):
            tau, ratio = compute_tau_e(
                edge_length_m=float(row.length),
                observed_speed_kph=float(row.observed_speed_kph),
                free_flow_speed_kph=float(row.free_flow_speed_kph),
                free_flow_travel_time_s=float(row.travel_time),
            )
            travel_times.append(tau)
            congestion_ratios.append(ratio)

        filled["travel_time_s"] = travel_times
        filled["congestion_ratio"] = congestion_ratios
        profile_parts.append(filled)

    profile_frame = pd.concat(profile_parts, ignore_index=True)
    profile_frame = profile_frame[[*PROFILE_COLUMNS, "cost_source"]]
    return TrafficProfile(edge_stats=profile_frame, time_buckets=time_buckets), mapping


def build_traffic_profile_from_file(
    graph: nx.MultiDiGraph,
    observations_path: str | Path,
    *,
    time_buckets: tuple[str, ...] = DEFAULT_TIME_BUCKETS,
    max_distance_m: float = 50.0,
) -> tuple[TrafficProfile, pd.DataFrame]:
    """Convenience wrapper: load observations from disk and build a profile."""
    observations = load_traffic_observations(observations_path)
    return build_traffic_profile(
        graph,
        observations,
        time_buckets=time_buckets,
        max_distance_m=max_distance_m,
    )


def save_traffic_profile(profile: TrafficProfile, path: str | Path) -> Path:
    """Persist a traffic profile to parquet."""
    return profile.save(path)


def load_traffic_profile(path: str | Path) -> TrafficProfile:
    """Load a traffic profile from parquet."""
    return TrafficProfile.load(path)
