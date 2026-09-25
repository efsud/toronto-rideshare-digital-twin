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

## Toronto Open Data auto-normalization

`traffic/ingest.py` automatically detects common Toronto Open Data column names and
normalizes them via `normalize_toronto_open_data()`. Supported aliases include:

| Open Data column | Normalized column |
|------------------|-------------------|
| `location_id`, `station_id`, `site_id` | `observation_id` |
| `LATITUDE`, `lat`, `y` | `latitude` |
| `LONGITUDE`, `lon`, `lng`, `x` | `longitude` |
| `timestamp`, `date_time`, `date`+`time` | `datetime` |
| `avg_speed`, `average_speed`, `speed_kmh` | `speed_kph` |

If no file exists in `data/raw/`, `examples/build_traffic_profile.py` falls back to
`data/synthetic/traffic_observations_sample.csv`.

## Expected normalized schema

`traffic/ingest.py` auto-normalizes common Toronto Open Data column names (e.g.
`location_id`, `avg_speed`, `LATITUDE`/`LONGITUDE`). If your download uses other
names, convert it to this schema or extend the adapter in `traffic/ingest.py`:

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
