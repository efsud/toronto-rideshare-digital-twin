# Toronto Ride-Hailing Marketplace Digital Twin

A research-grade simulator for traffic-aware rider–driver matching, two-sided pricing,
driver incentives, and spatial supply–demand balancing on Toronto's street network.

**Status:** v0.3 — network, time-dependent traffic, H3 zones, baseline marketplace simulation,
rule-based policies, experiment runner, and Streamlit skeleton implemented.
Full OR-Tools optimization, policy comparison dashboards, and SUMO remain in progress.

## What works today

| Layer | Capability |
|-------|------------|
| Network | Download Toronto OSM drive graph, impute speeds, save/load GraphML |
| Routing | Shortest free-flow path; route distance and travel time |
| Traffic | Ingest observations, map to edges, compute tau_e(t), route by departure time |
| Zones | H3 cells for spatial marketplace aggregation |
| Demand/Supply | Synthetic trip generator and driver fleet initialization |
| Simulation | Discrete clock, greedy matching, waiting times, baseline metrics |
| Policies | Independent rider adjustments and driver bonuses (rule-based) |
| Experiments | YAML-driven baseline runs with JSON results |
| Dashboard | Streamlit skeleton (`dashboard/app.py`) |
| Tests | 21 unit tests (synthetic graphs, no live OSM in CI) |

## Architecture

```text
OpenStreetMap → network/ → GraphML
                    ↓
              traffic/ → edge_traffic_profile.parquet
                    ↓
              routing (free-flow or travel_time_t)
                    ↓
         [future] zones → demand/supply → marketplace → simulation → policies
```

## Environment setup

Python **3.12** is recommended. Python 3.11+ is supported.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install "pyproj>=3.5,<3.7"   # workaround if 3.7 wheels unavailable on your platform
pip install -e ".[dev,visualization,optimization]"
```

Or use the helper script:

```bash
bash setup.sh
```

Copy `.env.example` to `.env` if you add API keys later. Never commit `.env`.

## Quick start

```bash
# 1. Build road network (internet required, one-time)
python examples/download_toronto_network.py

# 2. Build traffic profile from synthetic or raw observations
python examples/build_traffic_profile.py

# 3. Compare routes at 07:00, 08:30, 12:00, 17:00
python examples/time_dependent_route_demo.py

# 4. Optional map + bar chart
pip install -e ".[visualization]"
python examples/plot_time_dependent_routes.py
```

## Tests and lint

```bash
pytest
ruff check src tests examples scripts
python scripts/task_00_validate_env.py
```

## Core equation

```text
T_trip(r, t) = min over paths P from o_r to d_r  sum_{e in P} tau_e(t)
```

- **v0.1:** tau_e = free-flow `travel_time`
- **v0.2:** tau_e(t) from traffic profile (`travel_time_t` at departure bucket t)

Edge costs are frozen at trip departure (no within-trip dynamic routing yet).

## Configuration

| File | Purpose |
|------|---------|
| `configs/baseline.yaml` | Baseline simulation settings |
| `configs/morning_peak.yaml` | Morning-peak traffic scenario |
| `configs/policy_bounds.yaml` | Future pricing/subsidy bounds |
| `configs/scenarios/` | Traffic/demand scenario stubs |
| `configs/experiments/` | Reproducible experiment stubs |

## Data policy

| Type | Source | Label |
|------|--------|-------|
| Road network | OpenStreetMap via OSMnx | Observed (public) |
| Traffic (default demo) | `data/synthetic/traffic_observations_sample.csv` | Synthetic |
| Traffic (production) | Toronto Open Data — see `data/raw/README.md` | Observed (when downloaded) |
| Future rider OD | Synthetic calibrated to public patterns | Synthetic (documented) |

We do **not** reproduce Uber/Lyft proprietary pricing. Behavioral elasticities are
configurable assumptions unless empirically estimated.

## Artifacts

Task outputs live under `artifacts/task_XX_name/`. See `artifacts/README.md`.

## Demo (portfolio)

Reproduce key visualizations after setup:

```bash
# Policy comparison P0–P7 (chart + JSON)
python examples/generate_policy_comparison_demo.py
# → artifacts/task_policy_compare/policy_comparison_chart.png
# → artifacts/task_policy_compare/policy_comparison_p0_p7.json

# Baseline marketplace experiment
python examples/run_baseline_experiment.py
# → results/experiments/

# Time-dependent routing (requires network + profile)
python examples/time_dependent_route_demo.py

# Sensitivity sweep
python examples/run_sensitivity.py
# → artifacts/task_sensitivity/sensitivity_results.json

# Interactive dashboard
streamlit run dashboard/app.py
```

| Artifact | Path |
|----------|------|
| Policy comparison chart | `artifacts/task_policy_compare/policy_comparison_chart.png` |
| Policy comparison data | `artifacts/task_policy_compare/policy_comparison_p0_p7.json` |
| Big picture doc | `docs/Toronto_Rideshare_Digital_Twin_Big_Picture.docx` |
| PR readiness | `artifacts/PR_READINESS.md` |
| SUMO integration guide | `docs/SUMO.md` |
| RL benchmark outline | `docs/RL_BENCHMARK.md` |

## Marketplace experiment

```bash
python examples/run_baseline_experiment.py
python examples/run_policy_comparison_demo.py
python examples/generate_demo_visualization.py
streamlit run dashboard/app.py
python scripts/final_validation.py
```

## Demo artifacts

After running the demo script, open:

| Artifact | Description |
|----------|-------------|
| `artifacts/task_demo/demo_summary.png` | Policy bar chart + sensitivity heatmap |
| `artifacts/task_demo/policy_comparison.json` | P0–P7 metrics on same seed |
| `artifacts/task_policy_compare/policy_comparison_chart.png` | Standalone policy chart |
| `docs/Toronto_Rideshare_Digital_Twin_Big_Picture.docx` | Full project summary (Word) |

Regenerate the Word summary:

```bash
python scripts/export_big_picture_docx.py
```

## Roadmap (high level)

1. ~~Network + free-flow routing~~ (done)
2. ~~Time-dependent traffic tau_e(t)~~ (done)
3. ~~H3 zones, demand, drivers, simulation clock~~ (baseline done)
4. ~~Greedy matching + rule policies~~ (baseline done)
5. OR-Tools LP optimization, network-based routing in matching, policy comparison UI
6. Full Streamlit map layers, repeated stochastic experiments, sensitivity analysis
7. Optional SUMO / advanced ML / RL benchmarks (see `docs/SUMO.md`)

## Limitations

- Sparse synthetic traffic → many edges use highway/citywide fallbacks
- No rider/driver marketplace loop yet
- No SUMO integration yet
- Dashboard not yet wired to live simulation

## Attribution

Road-network data from OpenStreetMap. Retain OSM attribution in published maps.
