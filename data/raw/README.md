# Raw Toronto Traffic Data

Place downloaded Toronto traffic observation files in this folder.

## Recommended source

Toronto Open Data portal:

- [Permanent Count Station Locations](https://open.toronto.ca/dataset/permanent-count-station-locations/)
- [Traffic Volumes at Intersections](https://open.toronto.ca/dataset/traffic-volumes-at-intersections/)

Download CSV or GeoJSON exports and save them here, for example:

```text
data/raw/toronto_traffic_observations.csv
```

## Expected normalized schema

If your download uses different column names, convert it to this schema before building
the traffic profile (or extend `traffic/ingest.py` with a dataset-specific adapter):

| Column | Type | Example |
|--------|------|---------|
| `observation_id` | string | `PCS_12345` |
| `latitude` | float | `43.6532` |
| `longitude` | float | `-79.3832` |
| `datetime` | ISO timestamp | `2024-03-15T08:00:00` |
| `speed_kph` | float | `28.5` |
| `volume` | int (optional) | `1200` |
| `source` | string | `toronto_open_data` |

## Build the processed profile

After downloading the Toronto drive graph:

```bash
python examples/build_traffic_profile.py
```

This writes:

- `data/processed/edge_traffic_profile.parquet`
- `data/processed/traffic_edge_map.parquet`

## Synthetic sample for tests

Committed sample data lives at:

```text
data/synthetic/traffic_observations_sample.csv
```

Unit tests use tiny in-memory graphs and do not require files from this folder.
