"""Measured-parameter fitting with explicit group holdout and scoped claims."""

import hashlib

import numpy as np
from scipy.optimize import minimize
from scipy.special import expit


def group_split(frame, group_column, training_fraction=0.8):
    if group_column not in frame or frame[group_column].isna().any():
        raise ValueError("Every observation needs a nonmissing group identifier")
    groups = sorted(
        frame[group_column].astype(str).unique(),
        key=lambda x: hashlib.sha256(x.encode()).hexdigest(),
    )
    if len(groups) < 5:
        raise ValueError("At least five independent groups are required")
    cutoff = max(1, min(len(groups) - 1, int(training_fraction * len(groups))))
    mask = frame[group_column].astype(str).isin(groups[:cutoff])
    return frame.loc[mask].copy(), frame.loc[~mask].copy()


def fit_speed_scales(training):
    """Fit observed speed = bucket scale × free-flow speed, equal weight per site.

    The coefficient minimizes squared speed error on training observations only.
    Bounds [0.2, 1.5] are declared model constraints, not learned thresholds.
    """
    required = {"site_id", "time_bucket", "speed_kph", "free_flow_speed_kph"}
    if not required <= set(training) or training.empty:
        raise ValueError("Nonempty matched speed observations and site IDs required")
    values = training[["speed_kph", "free_flow_speed_kph"]].to_numpy(float)
    if not np.isfinite(values).all() or (values <= 0).any():
        raise ValueError("Speeds must be finite and positive")
    if training.site_id.isna().any() or training.time_bucket.isna().any():
        raise ValueError("Site and bucket must be present")
    if training.site_id.nunique() < 3:
        raise ValueError("At least three training sites required")

    def coefficient(frame):
        x, y = frame.free_flow_speed_kph.to_numpy(), frame.speed_kph.to_numpy()
        w = 1 / frame.groupby("site_id").site_id.transform("size").to_numpy()
        return float(np.clip(np.sum(w * x * y) / np.sum(w * x * x), 0.2, 1.5))

    global_scale = coefficient(training)
    bucket_scales = {}
    for bucket, frame in training.groupby("time_bucket"):
        bucket_scales[bucket] = coefficient(frame) if frame.site_id.nunique() >= 3 else global_scale
    return {
        "global_scale": global_scale,
        "bucket_scales": bucket_scales,
        "training_rows": len(training),
        "training_sites": int(training.site_id.nunique()),
        "objective": "equal-site weighted squared speed error",
        "bounds": [0.2, 1.5],
    }


def predict_speeds(frame, fit):
    return frame.free_flow_speed_kph.to_numpy(float) * frame.time_bucket.map(
        fit["bucket_scales"]
    ).fillna(fit["global_scale"]).to_numpy(float)


def fit_rider_response(observations):
    """Fit grouped binomial total-price acceptance, with held-out group evidence.

    Each row contains group_id, price_cad, accepted and offered. Raw ride requests
    may use offered=1. Do not pass volume counts or generated requests as empirical
    acceptance observations. The caller must retain and disclose provenance.
    """
    required = {"group_id", "price_cad", "accepted", "offered"}
    if not required <= set(observations):
        raise ValueError(f"Required rider fields: {sorted(required)}")
    data = observations.copy()
    values = data[["price_cad", "accepted", "offered"]].to_numpy(float)
    if not np.isfinite(values).all() or (values < 0).any():
        raise ValueError("Finite nonnegative rider fields required")
    if (data.offered <= 0).any() or (data.accepted > data.offered).any():
        raise ValueError("Accepted must be between zero and a positive offered count")
    if ((values[:, 1:] % 1) != 0).any():
        raise ValueError("Offer and acceptance counts must be integers")
    training, test = group_split(data, "group_id")
    if training.price_cad.nunique() < 2 or not 0 < training.accepted.sum() < training.offered.sum():
        raise ValueError("Training needs varied prices and both accepted and declined offers")

    def loss(theta, frame):
        score = theta[0] - theta[1] * frame.price_cad.to_numpy()
        return float(
            np.sum(
                frame.offered.to_numpy() * np.logaddexp(0, score)
                - frame.accepted.to_numpy() * score
            )
            / frame.offered.sum()
        )

    result = minimize(
        loss, [2, 0.08], args=(training,), method="L-BFGS-B", bounds=[(-10, 10), (0, 2)]
    )
    if not result.success or not np.isfinite(result.x).all():
        raise ValueError(f"Rider fitting failed: {result.message}")
    probability = expit(result.x[0] - result.x[1] * test.price_cad.to_numpy())
    rate = training.accepted.sum() / training.offered.sum()
    baseline_loss = -float(
        np.sum(test.accepted * np.log(rate) + (test.offered - test.accepted) * np.log1p(-rate))
        / test.offered.sum()
    )
    return {
        "status": "fit_with_group_holdout",
        "scope": "rider acceptance conditional on total price",
        "parameters": {
            "rider_intercept": float(result.x[0]),
            "rider_price_per_cad": float(result.x[1]),
        },
        "bounds": {"rider_intercept": [-10, 10], "rider_price_per_cad": [0, 2]},
        "training_groups": int(training.group_id.nunique()),
        "test_groups": int(test.group_id.nunique()),
        "group_overlap": sorted(set(training.group_id) & set(test.group_id)),
        "test_offers": int(test.offered.sum()),
        "test_log_loss": loss(result.x, test),
        "constant_training_rate_log_loss": baseline_loss,
        "test_rate_mae": float(
            np.average(abs(probability - test.accepted / test.offered), weights=test.offered)
        ),
        "limitation": (
            "Associational fit; prices may be confounded with trip and market characteristics"
        ),
    }


def calibrated_road_scenario(source, report_path):
    """Apply only a checksum-matched road profile; leave behavioral assumptions intact."""
    import json
    from pathlib import Path

    from toronto_rideshare.manifest import file_checksum
    from toronto_rideshare.scenario import ScenarioConfig

    report = json.loads(Path(report_path).read_text())
    config = ScenarioConfig.from_source(source).as_dict()
    if report.get("status") != "calibrated_speed_parameters_with_holdout":
        raise ValueError("Expected a road-speed calibration report with holdout evidence")
    profile = report.get("profile_path", "")
    expected = report.get("profile_sha256")
    if not expected or file_checksum(profile) != expected:
        raise ValueError("Calibrated profile missing or checksum differs from the report")
    if file_checksum(config["network"]["graph_path"]) != report["provenance"]["graph_sha256"]:
        raise ValueError("Scenario road graph differs from the calibration graph")
    config["network"].update(mode="network_research", traffic_profile_path=profile)
    return ScenarioConfig.from_source(config).as_dict()
