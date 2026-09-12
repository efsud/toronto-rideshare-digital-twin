import pandas as pd

from toronto_rideshare.traffic.qa import mapping_quality_report


def test_mapping_quality_report() -> None:
    mapping = pd.DataFrame({"observation_id": ["A", "B"]})
    observations = pd.DataFrame({"observation_id": ["A", "B", "C"]})
    profile = pd.DataFrame(
        {
            "time_bucket": ["08:30", "08:30"],
            "n_observations": [1, 0],
            "congestion_ratio": [1.5, 1.0],
        }
    )
    report = mapping_quality_report(mapping, observations, profile)
    assert report["n_observations_input"] == 3
    assert report["n_observations_mapped"] == 2
    assert report["mapping_rate"] == 2 / 3
