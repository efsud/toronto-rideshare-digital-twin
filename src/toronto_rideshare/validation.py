"""Evidence-aware validation. Comparison is not proof of predictive validity."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from pathlib import Path

import pandas as pd


@dataclass(frozen=True, slots=True)
class DatasetProvenance:
    dataset_name: str
    source_url: str
    retrieved_at: str
    license_name: str
    local_path: str
    observed: bool = True


@dataclass(frozen=True, slots=True)
class ValidationReport:
    status: str
    provenance: dict | None
    metric_errors: dict[str, float]
    note: str


class TorontoPublicDataAdapter:
    def __init__(self, provenance: DatasetProvenance) -> None:
        self.provenance = provenance

    def load_csv(self, *, required_columns=()) -> pd.DataFrame:
        frame = pd.read_csv(self.provenance.local_path)
        missing = set(required_columns) - set(frame.columns)
        if missing:
            raise ValueError(f"Observed dataset missing columns: {sorted(missing)}")
        return frame


def validate_aggregate_metrics(
    simulated, observed=None, *, provenance=None, criteria=None, criteria_description=None
) -> ValidationReport:
    source = asdict(provenance) if provenance else None
    if observed is None:
        return ValidationReport(
            "not_evaluated", source, {}, "No observed comparison; not calibration evidence."
        )
    overlap = sorted(set(simulated) & set(observed))
    complete = provenance and all(
        str(getattr(provenance, key)).strip()
        for key in ("dataset_name", "source_url", "retrieved_at", "license_name", "local_path")
    )
    if (
        not overlap
        or not complete
        or not all(
            math.isfinite(simulated[key]) and math.isfinite(observed[key]) for key in overlap
        )
        or (provenance.observed and not Path(provenance.local_path).is_file())
    ):
        return ValidationReport(
            "insufficient_data",
            source,
            {},
            "Finite overlapping metrics and complete source evidence required.",
        )
    errors = {key: simulated[key] - observed[key] for key in overlap}
    if not provenance.observed:
        return ValidationReport("synthetic_benchmark", source, errors, "Synthetic comparison only.")
    status = "compared_with_observed"
    if criteria:
        if not criteria_description or not set(criteria) <= set(errors):
            raise ValueError("Document criteria and supply every specified metric")
        if not all(math.isfinite(v) and v >= 0 for v in criteria.values()):
            raise ValueError("Criteria must be finite nonnegative absolute error bounds")
        if all(abs(errors[k]) <= bound for k, bound in criteria.items()):
            status = "meets_stated_benchmark_criteria"
    return ValidationReport(
        status,
        source,
        errors,
        criteria_description or "Signed errors; no acceptance criterion asserted.",
    )
