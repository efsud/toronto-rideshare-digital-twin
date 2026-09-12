"""Load and clean Toronto traffic observation files."""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import pandas as pd

from toronto_rideshare.traffic.models import DEFAULT_TIME_BUCKETS

TORONTO_BOUNDS = {
    "min_lat": 43.58,
    "max_lat": 43.86,
    "min_lon": -79.64,
    "max_lon": -79.12,
}

REQUIRED_COLUMNS = {"observation_id", "latitude", "longitude", "datetime"}


def _snap_to_time_bucket(timestamp: pd.Timestamp) -> str:
    """Map an observation timestamp to the nearest standard departure bucket."""
    minutes = int(timestamp.hour) * 60 + int(timestamp.minute)
    bucket_minutes = []
    for label in DEFAULT_TIME_BUCKETS:
        hour, minute = label.split(":")
        bucket_minutes.append((int(hour) * 60 + int(minute), label))
    _, nearest_label = min(bucket_minutes, key=lambda item: abs(item[0] - minutes))
    return nearest_label


def load_traffic_observations(path: str | Path) -> gpd.GeoDataFrame:
    """Load raw traffic observations from CSV or GeoJSON into a GeoDataFrame."""
    input_path = Path(path)
    if not input_path.exists():
        raise FileNotFoundError(f"Traffic observation file not found: {input_path}")

    suffix = input_path.suffix.lower()
    if suffix == ".csv":
        frame = pd.read_csv(input_path)
    elif suffix in {".geojson", ".json"}:
        return gpd.read_file(input_path)
    else:
        msg = f"Unsupported traffic file format: {suffix}. Use .csv or .geojson."
        raise ValueError(msg)

    missing = REQUIRED_COLUMNS - set(frame.columns)
    if missing:
        msg = f"Traffic file missing required columns: {sorted(missing)}"
        raise ValueError(msg)

    frame["datetime"] = pd.to_datetime(frame["datetime"], utc=True, errors="coerce")
    geometry = gpd.points_from_xy(frame["longitude"], frame["latitude"], crs="EPSG:4326")
    return gpd.GeoDataFrame(frame, geometry=geometry, crs="EPSG:4326")


def clean_observations(observations: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Drop invalid rows and restrict observations to the Toronto bounding box."""
    cleaned = observations.copy()
    cleaned = cleaned.dropna(subset=["observation_id", "latitude", "longitude", "datetime"])

    if "speed_kph" in cleaned.columns:
        cleaned = cleaned.dropna(subset=["speed_kph"])
        cleaned = cleaned[cleaned["speed_kph"] > 0]

    bounds = TORONTO_BOUNDS
    cleaned = cleaned[
        cleaned["latitude"].between(bounds["min_lat"], bounds["max_lat"])
        & cleaned["longitude"].between(bounds["min_lon"], bounds["max_lon"])
    ]

    cleaned["observation_id"] = cleaned["observation_id"].astype(str)
    cleaned["time_bucket"] = cleaned["datetime"].map(_snap_to_time_bucket)
    cleaned["hour"] = cleaned["datetime"].dt.hour
    cleaned["minute"] = cleaned["datetime"].dt.minute

    if "source" not in cleaned.columns:
        cleaned["source"] = "unknown"

    return cleaned.reset_index(drop=True)


def normalize_toronto_open_data(frame: pd.DataFrame) -> pd.DataFrame:
    """Map common Toronto Open Data column names to the normalized schema."""
    column_map = {
        "location_id": "observation_id",
        "station_id": "observation_id",
        "lat": "latitude",
        "LATITUDE": "latitude",
        "lon": "longitude",
        "LONGITUDE": "longitude",
        "lng": "longitude",
        "timestamp": "datetime",
        "date_time": "datetime",
        "avg_speed": "speed_kph",
        "speed": "speed_kph",
        "volume": "volume",
    }
    normalized = frame.rename(columns={k: v for k, v in column_map.items() if k in frame.columns})
    if "observation_id" not in normalized.columns and "location_id" in frame.columns:
        normalized["observation_id"] = frame["location_id"].astype(str)
    if "source" not in normalized.columns:
        normalized["source"] = "toronto_open_data"
    missing = REQUIRED_COLUMNS - set(normalized.columns)
    if missing:
        msg = f"After normalization, still missing columns: {sorted(missing)}"
        raise ValueError(msg)
    return normalized
