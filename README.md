# Toronto Ride-Hailing Marketplace Digital Twin

A research/portfolio simulator for traffic-aware rider-driver matching, two-sided pricing,
driver incentives, and spatial supply-demand balancing on Toronto's street network.

## Version 0.1 scope

This initial repository implements only the **road-network foundation**:

- download Toronto's drivable OpenStreetMap network with OSMnx;
- impute free-flow road speeds;
- add edge-level free-flow travel times;
- save/load the graph as GraphML;
- find the nearest network nodes to arbitrary latitude/longitude points;
- calculate the minimum-travel-time route;
- report route distance and travel time;
- unit-test route summarization without requiring a live OpenStreetMap request.

Traffic observations, riders, drivers, pricing, matching, repositioning, optimization,
SUMO, and the Streamlit dashboard are intentionally deferred to later milestones.

## Architecture

```text
Toronto OpenStreetMap
        |
        v
src/toronto_rideshare/network
        |
        +-- build_network.py
        |      download -> speed -> travel_time -> GraphML
        |
        +-- routing.py
               coordinates -> nearest nodes -> shortest-time path
```

Future modules already have package placeholders under `src/toronto_rideshare/`.

## Environment setup

OSMnx 2.1.x requires Python 3.11 or newer. Python 3.12 is recommended for this project.

### Option A: standard `venv`

```bash
python3.12 -m venv .venv
source .venv/bin/activate          # macOS/Linux
python -m pip install --upgrade pip
pip install -e ".[dev,visualization,optimization]"
```

On Windows PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev,visualization,optimization]"
```

For the smallest Phase-1 install:

```bash
pip install -e ".[dev]"
```

## Run the tests

```bash
pytest
```

or:

```bash
pytest --cov=toronto_rideshare --cov-report=term-missing
```

## Lint

```bash
ruff check .
ruff format --check .
```

To apply formatting:

```bash
ruff format .
```

## Build the Toronto road graph

This step calls OpenStreetMap through OSMnx and therefore requires internet access.
It can take a while because Toronto's drive network is large.

```bash
python examples/download_toronto_network.py
```

It creates:

```text
data/processed/toronto_drive.graphml
```

Large generated graphs are git-ignored.

## Test a route

After downloading the graph:

```bash
python examples/route_demo.py
```

The demo returns:

- nearest origin network node;
- nearest destination network node;
- route distance in km;
- free-flow travel time in minutes;
- ordered route-node sequence.

## Core equation implemented in Version 0.1

For rider `r`, the base trip time is

```text
T_trip(r, t) = min over paths P from origin_r to destination_r
               sum over road edges e in P of tau_e(t)
```

In Version 0.1, `tau_e` is OSMnx's free-flow travel time. In the next milestone,
Toronto traffic observations will make this cost time dependent: `tau_e(t)`.

## Configuration

- `configs/baseline.yaml`: baseline project/network/simulation settings.
- `configs/morning_peak.yaml`: placeholder for the morning-peak traffic experiment.
- `configs/policy_bounds.yaml`: future rider-price, driver-bonus, subsidy, and objective bounds.

The pricing fields are placeholders and are not used by Version 0.1 yet.

## Next milestone

**Phase 2: Toronto traffic layer**

1. ingest Toronto observed speed/volume counts;
2. map observations to OSM edges;
3. construct time-indexed `travel_time_t` edge weights;
4. compare the fastest route for the same OD pair at 07:00, 08:30, 12:00, and 17:00;
5. add tests for time-dependent edge costs.

## Data and attribution

Road-network data come from OpenStreetMap through OSMnx. Any published maps or derived
network artifacts should retain appropriate OpenStreetMap attribution.
