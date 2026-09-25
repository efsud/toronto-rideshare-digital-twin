# Full-day three-policy experiment — September 25, 2026

**Scope:** 30 paired seeds (42–71), three policies, 90 complete synthetic 24-hour runs. The same request population, initial fleet and behavioral assumptions apply within each seed. Runs use illustrative straight-line travel; the separately fitted public road-speed profile is not used in this experiment. The synthetic daily scenario has 60 drivers, 1,200 potential opportunities, request probability 0.8, 5-minute decisions and a CAD 500 subsidy budget.

The experiment is reproducible with `python scripts/validate_daily_research.py`. Runtime on the development machine was about 63 seconds. Every run reconciled request populations, utilization bounds and the rider-payment/driver-earnings/contribution identity. Earlier integration checks also verified commitments plus subsidy settlement at every decision epoch.

## Outcomes and paired effects

| Policy | Completed trips | Realized pickup wait (min) | Platform contribution (CAD) | Subsidy settled (CAD) |
|---|---:|---:|---:|---:|
| P0 fixed-price baseline | 430.10 | 15.480 | 2311.93 | 0 |
| P5 repositioning | 429.40 | 15.126 | 2308.23 | 0 |
| Adaptive OD pricing | 422.57 | 15.442 | 2449.71 | 11.07 |

Paired 95% Student-t confidence intervals against P0:

| Effect | P5 minus P0 | Adaptive minus P0 |
|---|---|---|
| Completed trips | −0.70 [−1.72, +0.32] | −7.53 [−8.88, −6.19] |
| Realized pickup wait (min) | −0.354 [−0.490, −0.219] | −0.038 [−0.191, +0.114] |
| Platform contribution (CAD) | −3.70 [−9.66, +2.26] | +137.78 [+128.79, +146.77] |

The adaptive rule raises modeled contribution while reducing completed service in this scenario. Its mean wait improvement is not clear from the interval. P5 reduces wait among collected riders; its completed-trip difference is not clear. These are tradeoffs under assumed behavior, not a commercial recommendation or evidence of improved Toronto service. Wait covers collected riders only; it should be read alongside service, cancellations, price declines and unfinished trips. Contribution excludes operating costs. Intervals capture simulated seed variation, not calibration uncertainty or multiple-comparison adjustment.

Average adaptive subsidy use is far below the cap: sparse H3-level queues and initial uniform supply often produce small destination-transfer incentives. That is a property to inspect and tune, not something to conceal by selecting a favorable scenario. Policy gains and zone resolution are design assumptions. Do not change behavioral coefficients between policies to manufacture an apparent improvement.

## Controlled adaptive-response check

The same route with unchanged base fare CAD 18.85 is evaluated in two controlled market snapshots:

| Snapshot | Origin shortage | Destination shortage | Driver bonus | Rider payment |
|---|---:|---:|---:|---:|
| Morning, supply at origin | −3 | +4 | CAD 7.00 | CAD 13.85 |
| Evening, supply at destination | +5 | −4 | CAD 0.00 | CAD 21.35 |

The bonus disappears and the rider quote changes when moving that same driver into the destination is no longer helpful. This verifies the pricing response to reversed state. These are explicit software-test snapshots, not empirical traffic measurements or a claim of better system performance. The continuous daily runs separately exercise synthetic inbound/outbound demand reversal and evolving supply through completed trips.

The compact paired summary, resolved scenario, seeds and full-results fingerprint are committed under `docs/evidence/daily_30_seed_summary.json`. The full local output includes hourly KPI trajectories and run manifests. Road-speed calibration evidence is separate in `CALIBRATION.md`.
