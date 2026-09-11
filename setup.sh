#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="${PYTHON_BIN:-python3.12}"

"$PYTHON_BIN" -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e ".[all]"

echo "Environment ready. Activate it later with: source .venv/bin/activate"
echo "Run tests with: pytest"
