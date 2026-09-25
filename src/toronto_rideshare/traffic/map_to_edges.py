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
    from shapely.geometry import LineString

    for index, row in edges.iterrows():
        coords = list(row.geometry.coords)
        origin = graph.nodes[row.u]
        distance_start = (coords[0][0] - origin["x"]) ** 2 + (coords[0][1] - origin["y"]) ** 2
        distance_end = (coords[-1][0] - origin["x"]) ** 2 + (coords[-1][1] - origin["y"]) ** 2
        if distance_end < distance_start:
            edges.at[index, "geometry"] = LineString(coords[::-1])
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
    radii = [max_distance_m]
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
    joined["ambiguous_match"] = joined.duplicated("observation_id", keep=False)
    if "direction" in joined:
        import numpy as np

        bearings = {
            "NB": 0,
            "NE": 45,
            "EB": 90,
            "SE": 135,
            "SB": 180,
            "SW": 225,
            "WB": 270,
            "NW": 315,
        }
        geometry_by_edge = {
            (int(r.u), int(r.v), int(r.key)): r.geometry for r in metric_edges.itertuples()
        }

        def compatible(row):
            expected = bearings.get(str(row.direction).upper())
            if expected is None:
                return True
            geometry = geometry_by_edge[int(row.u), int(row.v), int(row.key)]
            a, b = geometry.coords[0], geometry.coords[-1]
            bearing = np.degrees(np.arctan2(b[0] - a[0], b[1] - a[1])) % 360
            return abs((bearing - expected + 180) % 360 - 180) <= 60

        joined = joined[joined.apply(compatible, axis=1)].copy()
        joined["ambiguous_match"] = joined.duplicated("observation_id", keep=False)
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

    metric_obs = observations.to_crs("EPSG:26917")
    metric_edges = edges.to_crs("EPSG:26917")

    joined = _nearest_with_fallback(
        metric_obs,
        metric_edges,
        max_distance_m=max_distance_m,
    )

    if joined.empty:
        return pd.DataFrame(columns=list(EDGE_MAP_COLUMNS))

    mapping = joined[
        ["observation_id", "u", "v", "key", "match_distance_m", "ambiguous_match"]
    ].copy()
    if "highway" in joined.columns:
        mapping["highway"] = joined["highway"].astype(str)
    else:
        mapping["highway"] = "unknown"

    mapping["u"] = mapping["u"].astype(int)
    mapping["v"] = mapping["v"].astype(int)
    mapping["key"] = mapping["key"].astype(int)
    mapping["observation_id"] = mapping["observation_id"].astype(str)
    mapping["direction_confidence"] = (
        "bearing-filtered" if "direction" in observations else "unknown"
    )
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

    if "ambiguous_match" in mapping:
        mapping = mapping[~mapping["ambiguous_match"]]
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
