"""Honest calibration/validation hooks for local Toronto public datasets."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import pandas as pd


@dataclass(frozen=True, slots=True)
class DatasetProvenance:
    """Minimum provenance required before observed-data validation is reported."""

    dataset_name: str
    source_url: str
    retrieved_at: str
    license_name: str
    local_path: str
    observed: bool = True


@dataclass(frozen=True, slots=True)
class ValidationReport:
    status: str
    provenance: dict[str, Any] | None
    metric_errors: dict[str, float]
    note: str


class TorontoPublicDataAdapter:
    """Load a local export while keeping source and retrieval metadata attached."""

    def __init__(self, provenance: DatasetProvenance) -> None:
        self.provenance = provenance

    def load_csv(self, *, required_columns: tuple[str, ...] = ()) -> pd.DataFrame:
        path = Path(self.provenance.local_path)
        if not path.exists():
            raise FileNotFoundError(
                f"Observed dataset is not local: {path}. Download it from "
                f"{self.provenance.source_url} and retain its retrieval metadata."
            )
        frame = pd.read_csv(path)
        missing = set(required_columns) - set(frame.columns)
        if missing:
            raise ValueError(f"Observed dataset missing columns: {sorted(missing)}")
        return frame


def validate_aggregate_metrics(
    simulated: dict[str, float],
    observed: dict[str, float] | None = None,
    *,
    provenance: DatasetProvenance | None = None,
) -> ValidationReport:
    """Return errors only when real observed values and provenance are supplied."""
    if observed is None or provenance is None:
        return ValidationReport(
            status="uncalibrated",
            provenance=asdict(provenance) if provenance else None,
            metric_errors={},
            note=(
                "No observed Toronto comparison was supplied. Simulation outputs remain "
                "synthetic/assumed and are not calibration evidence."
            ),
        )
    overlap = sorted(set(simulated) & set(observed))
    return ValidationReport(
        status="validated_against_observed" if provenance.observed else "synthetic_benchmark",
        provenance=asdict(provenance),
        metric_errors={name: simulated[name] - observed[name] for name in overlap},
        note="Signed error is simulated minus comparison value.",
    )
