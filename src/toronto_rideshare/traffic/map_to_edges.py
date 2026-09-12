"""Map traffic observation points to nearest OSM graph edges."""

from __future__ import annotations

from typing import Any

import geopandas as gpd
import networkx as nx
import pandas as pd

from toronto_rideshare.traffic.models import EDGE_MAP_COLUMNS


def _ox() -> Any:
    import osmnx as ox

    return ox


def graph_edges_gdf(graph: nx.MultiDiGraph) -> gpd.GeoDataFrame:
    """Convert graph edges to a GeoDataFrame with u, v, key, and geometry."""
    ox = _ox()
    _, edges = ox.convert.graph_to_gdfs(graph)
    edges = edges.reset_index()
    if edges.crs is None:
        edges = edges.set_crs("EPSG:4326")
    return edges


def _nearest_with_fallback(
    metric_obs: gpd.GeoDataFrame,
    metric_edges: gpd.GeoDataFrame,
    *,
    max_distance_m: float,
) -> gpd.GeoDataFrame:
    """Try progressively wider search radii before giving up on an observation."""
    radii = [max_distance_m, max_distance_m * 2, max_distance_m * 5, max_distance_m * 10]
    joined_parts: list[gpd.GeoDataFrame] = []
    remaining = metric_obs.copy()

    for radius in radii:
        if remaining.empty:
            break
        batch = gpd.sjoin_nearest(
            remaining,
            metric_edges,
            how="inner",
            distance_col="match_distance_m",
            max_distance=radius,
        )
        if batch.empty:
            continue
        joined_parts.append(batch)
        matched_ids = set(batch["observation_id"].astype(str))
        remaining = remaining[~remaining["observation_id"].astype(str).isin(matched_ids)]

    if not joined_parts:
        return gpd.GeoDataFrame()

    joined = pd.concat(joined_parts, ignore_index=True)
    joined = joined.sort_values("match_distance_m").drop_duplicates(
        subset=["observation_id"], keep="first"
    )
    return joined


def map_observations_to_edges(
    observations: gpd.GeoDataFrame,
    edges: gpd.GeoDataFrame,
    *,
    max_distance_m: float = 50.0,
) -> pd.DataFrame:
    """Match each observation point to the nearest directed edge within max distance."""
    if observations.empty:
        return pd.DataFrame(columns=list(EDGE_MAP_COLUMNS))

    if observations.crs != edges.crs:
        observations = observations.to_crs(edges.crs)

    metric_obs = observations.to_crs("EPSG:3857")
    metric_edges = edges.to_crs("EPSG:3857")

    joined = _nearest_with_fallback(
        metric_obs,
        metric_edges,
        max_distance_m=max_distance_m,
    )

    if joined.empty:
        return pd.DataFrame(columns=list(EDGE_MAP_COLUMNS))

    mapping = joined[
        ["observation_id", "u", "v", "key", "match_distance_m"]
    ].copy()
    if "highway" in joined.columns:
        mapping["highway"] = joined["highway"].astype(str)
    else:
        mapping["highway"] = "unknown"

    mapping["u"] = mapping["u"].astype(int)
    mapping["v"] = mapping["v"].astype(int)
    mapping["key"] = mapping["key"].astype(int)
    mapping["observation_id"] = mapping["observation_id"].astype(str)
    return mapping.drop_duplicates(subset=["observation_id", "u", "v", "key"]).reset_index(
        drop=True
    )


def aggregate_edge_speeds(
    mapping: pd.DataFrame,
    observations: gpd.GeoDataFrame,
    *,
    time_bucket_col: str = "time_bucket",
) -> pd.DataFrame:
    """Aggregate mapped observation speeds by directed edge and time bucket."""
    if mapping.empty:
        return pd.DataFrame(
            columns=["u", "v", "key", time_bucket_col, "observed_speed_kph", "n_observations"]
        )

    obs_cols = ["observation_id", "speed_kph", time_bucket_col]
    merged = mapping.merge(
        observations[obs_cols],
        on="observation_id",
        how="inner",
    )
    merged = merged.dropna(subset=["speed_kph"])

    aggregated = (
        merged.groupby(["u", "v", "key", time_bucket_col], as_index=False)
        .agg(
            observed_speed_kph=("speed_kph", "median"),
            n_observations=("speed_kph", "count"),
        )
        .rename(columns={time_bucket_col: "time_bucket"})
    )
    aggregated["u"] = aggregated["u"].astype(int)
    aggregated["v"] = aggregated["v"].astype(int)
    aggregated["key"] = aggregated["key"].astype(int)
    return aggregated
