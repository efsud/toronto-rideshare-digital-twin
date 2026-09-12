"""Quality metrics for traffic observation → edge mapping."""

from __future__ import annotations

import pandas as pd


def mapping_quality_report(
    mapping: pd.DataFrame,
    observations: pd.DataFrame,
    profile: pd.DataFrame,
) -> dict[str, float | int]:
    """Summarize mapping coverage and direct observation support."""
    n_obs = len(observations)
    n_mapped = mapping["observation_id"].nunique() if not mapping.empty else 0
    n_edges_direct = int((profile["n_observations"] > 0).sum()) if not profile.empty else 0
    edge_rows = len(profile) if not profile.empty else 0

    return {
        "n_observations_input": n_obs,
        "n_observations_mapped": n_mapped,
        "mapping_rate": n_mapped / n_obs if n_obs else 0.0,
        "n_profile_edge_rows": edge_rows,
        "n_edges_with_direct_obs": n_edges_direct,
        "median_congestion_ratio": float(profile["congestion_ratio"].median())
        if not profile.empty
        else 1.0,
    }
