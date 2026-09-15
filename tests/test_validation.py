from toronto_rideshare.validation import DatasetProvenance, validate_aggregate_metrics


def test_missing_observed_data_is_explicitly_uncalibrated() -> None:
    report = validate_aggregate_metrics({"service_rate": 0.8})

    assert report.status == "uncalibrated"
    assert report.metric_errors == {}
    assert "not calibration evidence" in report.note


def test_synthetic_fixture_is_not_labeled_observed_validation() -> None:
    provenance = DatasetProvenance(
        dataset_name="analytical fixture",
        source_url="local://tests",
        retrieved_at="2026-09-15",
        license_name="test fixture",
        local_path="tests/fixtures/example.csv",
        observed=False,
    )

    report = validate_aggregate_metrics(
        {"mean_wait_min": 5.0},
        {"mean_wait_min": 4.5},
        provenance=provenance,
    )

    assert report.status == "synthetic_benchmark"
    assert report.metric_errors == {"mean_wait_min": 0.5}
