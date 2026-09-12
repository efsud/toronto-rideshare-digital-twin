# SUMO / TraCI Integration

SUMO is **not** implemented yet. The Python marketplace simulator runs first; SUMO validates micro-level traffic dynamics.

## Planned workflow

```text
Python sim (matching + tau_e(t))
        |
        v
Export trips/routes --> SUMO routes XML
        |
        v
TraCI feedback loop --> updated edge speeds
        |
        v
Compare Python tau_e(t) vs SUMO congestion ratios
```

## Step-by-step integration plan

1. **Export network** — Convert OSM GraphML to SUMO `.net.xml` via `netconvert` or OSMnx → SUMO pipeline.
2. **Export demand** — Write matched trips from `simulation/engine.py` as SUMO `.rou.xml` with departure times.
3. **Run SUMO** — `sumo -c toronto.sumocfg --tripinfo-output tripinfo.xml`
4. **TraCI hook** — Python script reads edge mean speeds each step and writes comparison parquet under `artifacts/task_sumo/`.
5. **Validation metric** — MAPE between Python `tau_e(t)` and SUMO edge travel times by bucket.

## Files to add (future)

| File | Purpose |
|------|---------|
| `scripts/export_sumo_routes.py` | Matched trips → SUMO routes |
| `configs/sumo/toronto.sumocfg` | SUMO simulation config |
| `scripts/run_sumo_validation.py` | TraCI comparison runner |

## Prerequisites

- SUMO >= 1.18 installed locally
- `SUMO_HOME` environment variable set
- Toronto drive graph already built (`data/processed/toronto_drive.graphml`)

Do not replace the marketplace architecture with SUMO; use it as an independent validation layer.
