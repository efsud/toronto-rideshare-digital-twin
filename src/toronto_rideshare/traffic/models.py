"""Data models for time-dependent traffic on OSM road edges."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

DEFAULT_TIME_BUCKETS: tuple[str, ...] = ("07:00", "08:30", "12:00", "17:00")

PROFILE_COLUMNS: tuple[str, ...] = (
    "u",
    "v",
    "key",
    "time_bucket",
    "observed_speed_kph",
    "free_flow_speed_kph",
    "travel_time_s",
    "congestion_ratio",
    "n_observations",
)

EDGE_MAP_COLUMNS: tuple[str, ...] = (
    "observation_id",
    "u",
    "v",
    "key",
    "match_distance_m",
    "highway",
)


@dataclass(frozen=True, slots=True)
class TimeBucket:
    """One departure-time period used for edge travel-time lookup."""

    label: str

    @staticmethod
    def from_departure_time(departure_time: str) -> TimeBucket:
        normalized = departure_time.strip()
        if len(normalized) == 4 and normalized[1] == ":":
            normalized = f"0{normalized}"
        if normalized not in DEFAULT_TIME_BUCKETS:
            msg = (
                f"Unsupported departure time {departure_time!r}. "
                f"Expected one of {DEFAULT_TIME_BUCKETS}."
            )
            raise ValueError(msg)
        return TimeBucket(label=normalized)


@dataclass(frozen=True, slots=True)
class TrafficObservation:
    """One traffic measurement at a sensor location."""

    observation_id: str
    latitude: float
    longitude: float
    datetime: pd.Timestamp
    speed_kph: float | None = None
    volume: int | None = None
    source: str = "unknown"


@dataclass(frozen=True, slots=True)
class EdgeTrafficStats:
    """Aggregated traffic stats for one directed edge and time bucket."""

    u: int
    v: int
    key: int
    time_bucket: str
    observed_speed_kph: float
    n_observations: int


@dataclass
class TrafficProfile:
    """Edge-level travel times tau_e(t) indexed by time bucket."""

    edge_stats: pd.DataFrame
    time_buckets: tuple[str, ...] = DEFAULT_TIME_BUCKETS

    def __post_init__(self) -> None:
        missing = set(PROFILE_COLUMNS) - set(self.edge_stats.columns)
        if missing:
            msg = f"TrafficProfile missing columns: {sorted(missing)}"
            raise ValueError(msg)

    def lookup_travel_time_s(self, u: int, v: int, key: int, time_bucket: str) -> float | None:
        mask = (
            (self.edge_stats["u"] == u)
            & (self.edge_stats["v"] == v)
            & (self.edge_stats["key"] == key)
            & (self.edge_stats["time_bucket"] == time_bucket)
        )
        rows = self.edge_stats.loc[mask, "travel_time_s"]
        if rows.empty:
            return None
        return float(rows.iloc[0])

    def save(self, path: str | Path) -> Path:
        output_path = Path(path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        self.edge_stats.to_parquet(output_path, index=False)
        return output_path.resolve()

    @classmethod
    def load(cls, path: str | Path) -> TrafficProfile:
        edge_stats = pd.read_parquet(path)
        buckets = tuple(sorted(edge_stats["time_bucket"].unique()))
        return cls(edge_stats=edge_stats, time_buckets=buckets)
