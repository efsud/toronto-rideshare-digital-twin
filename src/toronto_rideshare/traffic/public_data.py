"""Toronto SVC speed bins: approximate measured speeds, never inferred from volumes alone."""

from __future__ import annotations

import hashlib
import re

import geopandas as gpd
import numpy as np
import pandas as pd

from toronto_rideshare.traffic.ingest import clean_observations

SOURCE_URL = "https://open.toronto.ca/dataset/traffic-volumes-midblock-vehicle-speed-volume-and-classification-counts/"
PACKAGE_ID = "traffic-volumes-midblock-vehicle-speed-volume-and-classification-counts"


def normalize_speed_bins(raw: pd.DataFrame) -> gpd.GeoDataFrame:
    required = {
        "id",
        "count_id",
        "centreline_id",
        "time_start",
        "direction",
        "latitude",
        "longitude",
    }
    if missing := required - set(raw.columns):
        raise ValueError(f"SVC speed input missing fields: {sorted(missing)}")
    bins = [(column, re.fullmatch(r"vol_(\d+)_(\d+)kph", column)) for column in raw.columns]
    bins = [(name, float(m[1]), float(m[2])) for name, m in bins if m]
    if not bins:
        raise ValueError("No speed bins found; volume-only data cannot supply speeds")
    counts = raw[[name for name, _, _ in bins]].apply(pd.to_numeric, errors="coerce")
    valid = counts.notna().all(axis=1) & (counts >= 0).all(axis=1)
    volume = counts.sum(axis=1)
    valid &= volume > 0
    frame = raw.loc[valid].copy()
    selected = counts.loc[valid]
    frame["speed_kph"] = (
        selected.to_numpy() @ np.array([(a + b) / 2 for _, a, b in bins])
    ) / volume[valid]
    frame["speed_bin_low_kph"] = (selected.to_numpy() @ np.array([a for _, a, _ in bins])) / volume[
        valid
    ]
    frame["speed_bin_high_kph"] = (
        selected.to_numpy() @ np.array([b for _, _, b in bins])
    ) / volume[valid]
    frame["volume"] = volume[valid]
    frame["observation_id"] = frame["id"].astype(str)
    frame["datetime"] = frame["time_start"]
    frame["source"] = "Toronto SVC: speed-bin midpoint approximation"
    frame["study_id"] = frame["count_id"].astype(str)
    frame["site_id"] = frame["centreline_id"].astype(str)
    frame = gpd.GeoDataFrame(
        frame, geometry=gpd.points_from_xy(frame.longitude, frame.latitude), crs=4326
    )
    frame = clean_observations(frame)
    frame["study_date"] = frame["datetime"].dt.strftime("%Y-%m-%d")
    frame.attrs["qa"] = {
        "input_rows": len(raw),
        "usable_rows": len(frame),
        "excluded_rows": len(raw) - len(frame),
        "measurement": "speed-bin midpoint",
        "timezone": "America/Toronto",
    }
    return frame


def heldout_sites(observations: pd.DataFrame):
    """Keep all studies/dates/directions of a site in the same split."""
    sites = sorted(
        observations["site_id"].unique(),
        key=lambda site: hashlib.sha256(str(site).encode()).hexdigest(),
    )
    if len(sites) < 5:
        raise ValueError("At least five distinct sites are required for a held-out evaluation")
    cutoff = max(1, int(len(sites) * 0.8))
    training = observations[observations.site_id.isin(sites[:cutoff])].copy()
    test = observations[observations.site_id.isin(sites[cutoff:])].copy()
    return training, test


def error_metrics(observed, predicted):
    residual = np.asarray(predicted, dtype=float) - np.asarray(observed, dtype=float)
    if not len(residual) or not np.isfinite(residual).all():
        raise ValueError("Finite nonempty observed and predicted arrays required")
    return {
        "n": len(residual),
        "mae_kph": float(np.abs(residual).mean()),
        "rmse_kph": float(np.sqrt((residual**2).mean())),
        "bias_kph": float(residual.mean()),
    }


def evaluate_speed_baselines(observations):
    training, test = heldout_sites(observations)
    medians = training.groupby("time_bucket").speed_kph.median()
    global_speed = float(training.speed_kph.median())
    time_prediction = test.time_bucket.map(medians).fillna(global_speed)
    return {
        "status": "compared_with_observed",
        "scope": "Held-out-site speed-bin midpoint comparisons; not trip-time calibration",
        "split": {
            "method": "80/20 deterministic site holdout; all dates/directions kept together",
            "training_rows": len(training),
            "test_rows": len(test),
            "training_sites": int(training.site_id.nunique()),
            "test_sites": int(test.site_id.nunique()),
            "overlap_sites": sorted(set(training.site_id) & set(test.site_id)),
        },
        "global_training_median": error_metrics(test.speed_kph, np.full(len(test), global_speed)),
        "time_bucket_median": error_metrics(test.speed_kph, time_prediction),
        "free_flow": {"status": "not_evaluated", "reason": "Requires a matched OSM graph"},
        "measurement_uncertainty": (
            "Weighted bin midpoints; the 81–160 km/h bin is particularly broad"
        ),
        "acceptance_criteria": None,
        "rider_demand_driver_behavior": "not_evaluated",
    }
