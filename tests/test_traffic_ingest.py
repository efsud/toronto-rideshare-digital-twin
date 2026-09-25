import pandas as pd

from toronto_rideshare.traffic.ingest import normalize_toronto_open_data


def test_normalize_toronto_open_data_columns() -> None:
    raw = pd.DataFrame(
        {
            "location_id": ["PCS_1"],
            "LATITUDE": [43.65],
            "LONGITUDE": [-79.38],
            "timestamp": ["2024-03-15T08:00:00"],
            "avg_speed": [28.5],
        }
    )
    normalized = normalize_toronto_open_data(raw)
    assert "observation_id" in normalized.columns
    assert "latitude" in normalized.columns
    assert "longitude" in normalized.columns
    assert "datetime" in normalized.columns
    assert normalized.iloc[0]["source"] == "toronto_open_data"
