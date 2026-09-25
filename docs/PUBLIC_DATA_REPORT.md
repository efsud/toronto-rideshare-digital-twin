# Public-data evaluation — September 24, 2026

**Status: Compared with observed data. No acceptance threshold has been established.** The marketplace remains uncalibrated. This evaluation concerns approximate spot speeds, not complete trip times, ride demand, acceptance or earnings.

## Source and measurement

The City of Toronto [Midblock Vehicle Speed, Volume and Classification Counts](https://open.toronto.ca/dataset/traffic-volumes-midblock-vehicle-speed-volume-and-classification-counts/) provides short-duration studies, not a continuous citywide feed. The inspected `svc_raw_data_speed_2025_2029` resource contains `id`, `count_id`, `centreline_id`, location coordinates, `time_start`, `time_end`, direction and vehicle counts in speed bins (`vol_1_19kph` through `vol_81_160kph`). The adapter computes a count-weighted midpoint speed and retains weighted lower/upper bin bounds. Counts without speed bins cannot produce speed estimates. The widest bin is highly uncertain.

The first 50,000 resource rows were retrieved on September 24, 2026. This bounded, nonrandom sample is not representative of the city. The evaluation excludes 7,719 unusable/empty rows and retains 42,281 observations. Local timestamps use America/Toronto; ambiguous/nonexistent local times are excluded, while aware timestamps are converted. IDs, directions and measurement units remain available. Input SHA256 and graph/profile checksums are in [the machine-readable report](evidence/public_data_evaluation.json). Future downloads use a timestamped provenance sidecar.

## Holdout and geographic matching

Deterministic 80/20 site holdout keeps all dates, studies and directions at a site together: 34,032 training observations at 835 sites; 8,249 test observations at 209 sites; zero overlapping site IDs. This protects against same-site leakage, but nearby sites and shared road classes remain correlated.

Matching uses EPSG:26917 metres with a maximum 50 m separation and directed geometry. Cardinal direction must agree within 60 degrees when provided; ambiguous nearest-edge ties are excluded. It does not claim surveyed lane-level correspondence or search an arbitrarily wider radius when matching fails. The test cohort has 5,531 matched observations (67.1% of held-out rows); unmatched data do not contribute to network errors.

## Results

All metrics below use exactly the same 5,531 matched held-out observations, in km/h. Bias is predicted minus observed midpoint speed.

| Prediction | MAE | RMSE | Bias |
|---|---:|---:|---:|
| Training-derived traffic profile | 6.792 | 8.871 | +1.125 |
| OSM free-flow speed | 6.961 | 9.012 | +2.093 |
| Training time-bucket median | 7.570 | 9.698 | −0.231 |

Across all 8,249 held-out observations (a different cohort), the global training median MAE is 7.909 and the time-bucket median MAE is 7.796 km/h. Do not compare those values directly with the smaller mapped cohort as if coverage were identical.

The profile contains 292,528 edge/bucket records: 4,198 directly observed, 281,598 highway-class imputations, 6,732 citywide imputations. Only about 1.4% are directly observed. The small improvement over free flow is descriptive; no significance test or predeclared benchmark justifies a pass claim. No measured origin-to-destination trip times were evaluated.

## Network evidence and limitations

A fresh OSM download produced 27,443 nodes and 73,132 directed edges. A five-driver/five-request network smoke run using the training-only public profile completed in 19.58 seconds: four completed requests, one cancelled, and 36 evaluated route legs using time-dependent network routing. This is a connectivity/integration check, not a representative service forecast. Its manifest records the working code as dirty at measurement time.

The supplied 12-row synthetic CSV also completes ingestion/profile/routing integration. Only four observations match the full graph and those are ambiguous; its built profile consequently uses free-flow fallback. The example route is therefore identical across the four buckets (20.06 km / 22.8 min). This is explicitly not evidence of observed congestion.

Still needed: representative sampling across study dates and streets, improved matching confidence review, independent travel-time targets, predeclared acceptance criteria, sensitivity to speed-bin uncertainty, and separate empirical sources for demand and behavior. Run the commands in [REPRODUCE.md](REPRODUCE.md); do not silently replace missing speed data with volumes or synthetic observations.
