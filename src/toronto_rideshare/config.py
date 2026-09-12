"""Load YAML configuration files."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def load_config(path: str | Path = "configs/morning_peak.yaml") -> dict[str, Any]:
    """Load a project YAML config file."""
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with config_path.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)

    if not isinstance(data, dict):
        msg = f"Config file must contain a mapping at top level: {config_path}"
        raise ValueError(msg)
    return data
