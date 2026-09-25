# Reproduce the research checks

From the repository root, Python 3.11+:

```sh
python -m venv .venv
source .venv/bin/activate
pip install -e '.[all]'
ruff check src tests examples scripts dashboard
pytest --cov=toronto_rideshare --junitxml=results/tests.xml
streamlit run dashboard/app.py
```

Demo is offline. For an actual OSM graph and bounded City speed sample (network access required):

```sh
python examples/download_toronto_network.py
python scripts/fetch_public_sample.py
python scripts/evaluate_public_data.py
python scripts/benchmark_research.py
```

The fetch records resource URL, timestamp, checksum and sampling rule. Public evaluation uses site holdout, never test observations to fit the traffic profile. To run that profile in the dashboard, select Network research and set the traffic profile path to `data/processed/observed_training_profile.parquet`. The default profile filename may instead refer to the synthetic example; inspect provenance before using it.

A programmatic run uses the same scenario factory:

```python
from toronto_rideshare.experiments.runner import run_experiment
result = run_experiment({
    "project": {"random_seed": 42},
    "simulation": {"fleet_size": 20, "base_trip_count": 20},
    "network": {"mode": "demo"},
})
```

Export run evidence and comparison manifests from the UI. Large downloaded graphs and raw data are ignored by Git. Reviewed small reports are under `docs/evidence`. Runtime numbers depend on machine, caches and optional solver availability. Python traced allocations are not total process RSS. All changes are reviewable in draft PR #1; merging and hosting require separate release actions.

## Daily marketplace and calibration (v0.6 development)

The dashboard now defaults to `configs/experiments/full_day.yaml`: 00:00–24:00, three policies and shared driver choice. The earlier baseline YAML remains a legacy scenario. Reproduce the current evidence with:

```sh
python scripts/validate_daily_research.py
python scripts/calibrate_public_speeds.py
```

The first command executes 90 full-day runs (three policies × 30 paired seeds) and verifies a controlled shortage reversal. The second fits road-speed parameters on training sites and evaluates a separate site holdout, producing a deployable network profile. Raw data/graph prerequisites are listed above. Apply the profile using the Calibration panel after reviewing its scope. Behavioral fitting schema and commands are in `CALIBRATION.md`. Public speeds cannot calibrate driver preferences or ride demand.
