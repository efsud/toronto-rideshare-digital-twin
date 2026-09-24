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

SYNTHETIC_FALLBACK = Path("data/synthetic/traffic_observations_sample.csv")


def _snap_to_time_bucket(timestamp: pd.Timestamp) -> str:
    """Map an observation timestamp to the nearest standard departure bucket."""
    minutes = int(timestamp.hour) * 60 + int(timestamp.minute)
    bucket_minutes = []
    for label in DEFAULT_TIME_BUCKETS:
        hour, minute = label.split(":")
        bucket_minutes.append((int(hour) * 60 + int(minute), label))
    _, nearest_label = min(bucket_minutes, key=lambda item: abs(item[0] - minutes))
    return nearest_label


def normalize_toronto_open_data(frame: pd.DataFrame) -> pd.DataFrame:
    """Map common Toronto Open Data column names to the normalized schema."""
    column_map = {
        "location_id": "observation_id",
        "station_id": "observation_id",
        "site_id": "observation_id",
        "count_station_id": "observation_id",
        "lat": "latitude",
        "LATITUDE": "latitude",
        "y": "latitude",
        "lon": "longitude",
        "LONGITUDE": "longitude",
        "lng": "longitude",
        "x": "longitude",
        "timestamp": "datetime",
        "date_time": "datetime",
        "date_time_utc": "datetime",
        "datetime_utc": "datetime",
        "avg_speed": "speed_kph",
        "average_speed": "speed_kph",
        "speed": "speed_kph",
        "speed_kmh": "speed_kph",
        "volume": "volume",
        "total_volume": "volume",
    }
    normalized = frame.rename(columns={k: v for k, v in column_map.items() if k in frame.columns})

    if "observation_id" not in normalized.columns:
        for candidate in ("location_id", "station_id", "site_id", "count_station_id"):
            if candidate in frame.columns:
                normalized["observation_id"] = frame[candidate].astype(str)
                break

    if "latitude" not in normalized.columns and {"y", "x"} <= set(frame.columns):
        normalized["latitude"] = frame["y"]
        normalized["longitude"] = frame["x"]

    if "datetime" not in normalized.columns:
        for date_col, time_col in (("date", "time"), ("Date", "Time")):
            if date_col in frame.columns and time_col in frame.columns:
                normalized["datetime"] = pd.to_datetime(
                    frame[date_col].astype(str) + " " + frame[time_col].astype(str),
                    errors="coerce",
                )
                break

    if "source" not in normalized.columns:
        normalized["source"] = "toronto_open_data"

    missing = REQUIRED_COLUMNS - set(normalized.columns)
    if missing:
        msg = f"After normalization, still missing columns: {sorted(missing)}"
        raise ValueError(msg)
    return normalized


def _is_toronto_open_data(frame: pd.DataFrame) -> bool:
    """Heuristic: detect Toronto Open Data exports by column naming."""
    open_data_markers = {
        "location_id",
        "station_id",
        "site_id",
        "count_station_id",
        "avg_speed",
        "average_speed",
        "LATITUDE",
        "LONGITUDE",
    }
    return bool(open_data_markers & set(frame.columns))


def resolve_observations_path(path: str | Path | None = None) -> Path:
    """Return the best available observations file, falling back to synthetic sample."""
    if path is not None:
        candidate = Path(path)
        if candidate.exists():
            return candidate

    raw_dir = Path("data/raw")
    if raw_dir.is_dir():
        for pattern in ("*.csv", "*.geojson", "*.json"):
            matches = sorted(raw_dir.glob(pattern))
            if matches:
                return matches[0]

    if SYNTHETIC_FALLBACK.exists():
        return SYNTHETIC_FALLBACK

    msg = (
        "No traffic observations found. Place Toronto Open Data CSV/GeoJSON in "
        f"data/raw/ or ensure {SYNTHETIC_FALLBACK} exists."
    )
    raise FileNotFoundError(msg)


def load_traffic_observations(path: str | Path) -> gpd.GeoDataFrame:
    """Load raw traffic observations from CSV or GeoJSON into a GeoDataFrame."""
    input_path = Path(path)
    if not input_path.exists():
        raise FileNotFoundError(f"Traffic observation file not found: {input_path}")

    suffix = input_path.suffix.lower()
    if suffix == ".csv":
        frame = pd.read_csv(input_path)
        if _is_toronto_open_data(frame) or not REQUIRED_COLUMNS <= set(frame.columns):
            frame = normalize_toronto_open_data(frame)
        geometry = gpd.points_from_xy(frame["longitude"], frame["latitude"], crs="EPSG:4326")
        return gpd.GeoDataFrame(frame, geometry=geometry, crs="EPSG:4326")
    if suffix in {".geojson", ".json"}:
        gdf = gpd.read_file(input_path)
        if not REQUIRED_COLUMNS <= set(gdf.columns):
            raw = pd.DataFrame(gdf.drop(columns="geometry", errors="ignore"))
            normalized = normalize_toronto_open_data(raw)
            for col in normalized.columns:
                gdf[col] = normalized[col].values
        return gdf

    msg = f"Unsupported traffic file format: {suffix}. Use .csv or .geojson."
    raise ValueError(msg)


def clean_observations(observations: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Drop invalid rows and restrict observations to the Toronto bounding box."""
    cleaned = observations.copy()
    if "speed_kph" not in cleaned:
        raise ValueError("Speed observations are required; volume is not a speed measurement")

    def local_timestamp(value):
        try:
            ts = pd.Timestamp(value)
            if ts.tzinfo is None:
                return ts.tz_localize("America/Toronto", ambiguous="NaT", nonexistent="NaT")
            return ts.tz_convert("America/Toronto")
        except (ValueError, TypeError):
            return pd.NaT

    cleaned["datetime"] = pd.to_datetime(cleaned["datetime"].map(local_timestamp))
    for column in ("speed_kph", "latitude", "longitude"):
        cleaned[column] = pd.to_numeric(cleaned[column], errors="coerce")

    cleaned = cleaned.dropna(subset=["observation_id", "latitude", "longitude", "datetime"])

    if "speed_kph" in cleaned.columns:
        cleaned = cleaned.dropna(subset=["speed_kph"])
        cleaned = cleaned[cleaned["speed_kph"].between(0, float("inf"), inclusive="neither")]

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
