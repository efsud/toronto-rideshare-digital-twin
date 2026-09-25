# Calibration workflow and current evidence

Calibration means fitting declared parameters against suitable measurements. It does not make the whole marketplace a verified representation of Toronto. We use public data where it supports a measurement and label remaining assumptions, as requested.

## Road-speed parameters: fitted to public observations

`python scripts/calibrate_public_speeds.py` consumes the downloaded City Midblock speed-bin sample and OSM graph. To reproduce the downloads, first run `examples/download_toronto_network.py` and `scripts/fetch_public_sample.py`. The bounded sample is the first 50,000 rows, not a representative city sample.

The fitted model is `predicted speed = free-flow speed × departure-bucket scale`. Coefficients minimize squared speed error on training sites, with equal total weight per site and declared bounds 0.2–1.5. Buckets with fewer than three training sites use a training-only global coefficient. Speed-bin midpoints are approximate targets; the wide 81–160 km/h bin is particularly uncertain. Counts without speed bins are not usable speed targets.

All observations, directions and dates from a site stay together. Site holdout occurs before directed-road matching; ambiguous matches and those beyond 50 m are excluded. The resulting fit used 23,284 matched training rows at 801 sites. There is zero site overlap with evaluation. All profile costs are fitted predictions; none is mislabeled as a direct edge observation.

| Bucket | Fitted speed scale |
|---|---:|
| 07:00 | 0.98320 |
| 08:30 | 0.91955 |
| 12:00 | 0.92406 |
| 17:00 | 0.93294 |
| Global fallback | 0.94528 |

On the same 5,531 matched held-out rows, fitted MAE is 6.694 km/h, RMSE 8.541 km/h and bias −0.041 km/h. Free-flow MAE is 6.961, RMSE 9.012 and bias +2.093 km/h. These are exploratory results using the earlier site holdout, not a new external validation set or a predeclared passing criterion. They concern spot speeds, not end-to-end trip times. Overnight costs use the nearest available bucket; no continuous nighttime feed was inferred.

The script writes `results/speed_calibration.json`, `data/processed/calibrated_speed_profile.parquet` and a calibration sidecar with source, graph and profile checksums. **Understand the model → Calibration and parameter tuning** displays the fit and can apply it to a fresh network scenario. Applying verifies the profile and graph fingerprints. It preserves all rider/driver assumptions. Run manifests separately report the scoped road calibration.

## Rider acceptance: fitting workflow ready, empirical coefficients still assumed

The runnable interface is:

```sh
python scripts/calibrate_rider_response.py observations.csv --source "Dataset and measurement description"
```

Required CSV columns are `group_id,price_cad,accepted,offered`. A row can aggregate offers at a price or represent one offer with `offered=1`. Group related site/study/date observations so they cannot leak across train and holdout. `price_cad` must be the total shown price, not just a premium. Acceptance is binomial with probability `sigmoid(intercept − price_coefficient × total_price)`.

The routine needs at least five independent groups, varied prices and both acceptances and declines in training. It rejects invalid/nonfinite counts and fits bounded maximum likelihood. It reports held-out log loss, a constant training-rate baseline, group overlap and parameter bounds. A synthetic recovery test verifies the numerical procedure; it is not observational evidence. Pass `--synthetic` when running such a recovery dataset. Fitted coefficients can be entered in the shared behavior panel and applied equally to all three policies.

An association between price and acceptance may be confounded by trip distance, time, service quality or participant selection. This routine does not establish a causal price elasticity. No suitable observed Toronto rider-acceptance dataset has been loaded, so the default intercept 2 and price coefficient 0.08 remain assumptions. No synthetic values are promoted to empirical coefficients.

## What remains assumed

Driver menu-choice coefficients, request probability, regional/time demand weights, fleet size and initial distribution remain scenario assumptions. Public vehicle counts are not ride-hailing requests; bike-share OD records would not establish ride-hailing OD patterns. Road speeds cannot calibrate driver acceptance or gross earnings. The setup panel exposes tunable coefficients and the manifest records every applied value. Appropriate observations are required before those values can be described as empirically calibrated.

Policy incentive gains are design variables rather than behavioral parameters. Evaluate them against service, waiting, contribution and subsidy tradeoffs under paired seeds. A parameter setting that looks good inside the assumed simulator is not evidence that it is optimal in Toronto.
