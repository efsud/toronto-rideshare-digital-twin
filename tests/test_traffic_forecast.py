import pandas as pd

from toronto_rideshare.traffic.forecast import TrafficForecastModel


def test_traffic_forecast_baseline() -> None:
    obs = pd.DataFrame(
        {
            "datetime": pd.to_datetime(["2024-03-15 08:00", "2024-03-15 17:00"], utc=True),
            "speed_kph": [20.0, 40.0],
        }
    )
    model = TrafficForecastModel().fit(obs)
    assert model.predict_speed_kph(8) > 0.0
