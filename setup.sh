#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="${PYTHON_BIN:-python3.12}"

"$PYTHON_BIN" -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip

# pyproj 3.7+ may lack wheels on some macOS/Python combos; pin before geopandas/osmnx pull it in.
pip install "pyproj>=3.5,<3.7"
pip install -e ".[all]"

echo "Environment ready. Activate it later with: source .venv/bin/activate"
echo "Run tests with: pytest"
echo "Validate env with: python scripts/task_00_validate_env.py"
