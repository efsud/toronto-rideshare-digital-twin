"""Minimal sklearn baseline stub for traffic speed forecasting."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True, slots=True)
class TrafficForecastModel:
    """Ridge regression on hour-of-day for edge speed (baseline stub)."""

    coef_: np.ndarray | None = None
    intercept_: float = 30.0

    def fit(self, observations: pd.DataFrame) -> TrafficForecastModel:
        """Fit hour -> speed_kph ridge model."""
        from sklearn.linear_model import Ridge

        if observations.empty or "speed_kph" not in observations.columns:
            return TrafficForecastModel(intercept_=30.0)

        hours = observations["datetime"].dt.hour if "datetime" in observations.columns else 12
        x = np.array(hours).reshape(-1, 1)
        y = observations["speed_kph"].values
        model = Ridge(alpha=1.0)
        model.fit(x, y)
        return TrafficForecastModel(coef_=model.coef_, intercept_=float(model.intercept_))

    def predict_speed_kph(self, hour: int) -> float:
        if self.coef_ is None:
            return self.intercept_
        return float(self.intercept_ + self.coef_[0] * hour)
