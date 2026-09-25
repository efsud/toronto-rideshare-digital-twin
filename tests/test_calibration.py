import numpy as np
import pandas as pd
import pytest
from scipy.special import expit

from toronto_rideshare.calibration import (
    fit_rider_response,
    fit_speed_scales,
    group_split,
    predict_speeds,
)


def test_speed_calibration_recovers_known_scales_and_group_holdout():
    frame = pd.DataFrame(
        [
            {
                "site_id": str(site),
                "time_bucket": bucket,
                "free_flow_speed_kph": 30 + site,
                "speed_kph": (30 + site) * scale,
            }
            for site in range(20)
            for bucket, scale in (("07:00", 0.7), ("17:00", 0.9))
        ]
    )
    train, test = group_split(frame, "site_id")
    fit = fit_speed_scales(train)
    assert fit["bucket_scales"] == pytest.approx({"07:00": 0.7, "17:00": 0.9})
    assert not set(train.site_id) & set(test.site_id)
    np.testing.assert_allclose(predict_speeds(test, fit), test.speed_kph)
    corrupted_test = test.assign(speed_kph=999)
    assert fit == fit_speed_scales(train)  # test targets never enter fitting
    np.testing.assert_allclose(predict_speeds(corrupted_test, fit), test.speed_kph)


def test_rider_parameter_recovery_and_heldout_quality():
    rng = np.random.default_rng(51)
    rows = []
    for group in range(40):
        for price in (5, 15, 25, 40, 60):
            rows.append(
                {
                    "group_id": str(group),
                    "price_cad": price,
                    "offered": 100,
                    "accepted": int(rng.binomial(100, expit(2 - 0.08 * price))),
                }
            )
    result = fit_rider_response(pd.DataFrame(rows))
    assert result["parameters"]["rider_intercept"] == pytest.approx(2, abs=0.15)
    assert result["parameters"]["rider_price_per_cad"] == pytest.approx(0.08, abs=0.006)
    assert not result["group_overlap"]
    assert result["test_log_loss"] < result["constant_training_rate_log_loss"]


def test_calibration_refuses_unidentifiable_or_invalid_observations():
    with pytest.raises(ValueError):
        fit_rider_response(pd.DataFrame())
    same_price = pd.DataFrame(
        {
            "group_id": list("abcdef"),
            "price_cad": [10] * 6,
            "offered": [10] * 6,
            "accepted": [5] * 6,
        }
    )
    with pytest.raises(ValueError, match="varied prices"):
        fit_rider_response(same_price)
    with pytest.raises(ValueError, match="nonnegative"):
        fit_rider_response(same_price.assign(price_cad=float("inf")))
    with pytest.raises(ValueError, match="three training"):
        fit_speed_scales(
            pd.DataFrame(
                {
                    "site_id": ["a"],
                    "time_bucket": ["07:00"],
                    "speed_kph": [20],
                    "free_flow_speed_kph": [40],
                }
            )
        )


def test_apply_calibration_checks_artifacts_and_preserves_behavior(tmp_path):
    import json

    from toronto_rideshare.calibration import calibrated_road_scenario
    from toronto_rideshare.manifest import file_checksum
    from toronto_rideshare.scenario import ScenarioConfig

    graph, profile = tmp_path / "road.graphml", tmp_path / "profile.parquet"
    graph.write_bytes(b"graph fingerprint fixture")
    profile.write_bytes(b"profile fingerprint fixture")
    report = tmp_path / "report.json"
    report.write_text(
        json.dumps(
            {
                "status": "calibrated_speed_parameters_with_holdout",
                "profile_path": str(profile),
                "profile_sha256": file_checksum(profile),
                "provenance": {"graph_sha256": file_checksum(graph)},
            }
        )
    )
    source = ScenarioConfig.from_source({"network": {"graph_path": str(graph)}}).as_dict()
    applied = calibrated_road_scenario(source, report)
    assert applied["network"]["mode"] == "network_research"
    assert applied["behavior"] == source["behavior"]
    assert source["network"]["mode"] == "demo"
    profile.write_bytes(b"changed")
    with pytest.raises(ValueError, match="checksum"):
        calibrated_road_scenario(source, report)
