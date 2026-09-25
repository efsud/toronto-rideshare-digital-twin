# Full-day marketplace requirement audit

September 25, 2026. This audit follows the user's numbered objective, including the confirmed direction to use suitable public data and label unsupported assumptions. The preceding turns made implementation and verification progress; the model is not represented as an empirically validated Toronto marketplace.

| Requirement | Implemented behavior | Authoritative evidence |
|---|---|---|
| 0. Map legend | Persistent boundary, H3, pickup/destination, driver and route symbols; latest accepted/idle decision overlay | `presentation.py`, `dashboard/app.py`; Chrome reviewed map screenshots; dashboard and idle-overlay regressions |
| 1. At least a day | 00:00–24:00 is the shared default; full-day run button; explicit horizon states | Default/workspace equality test, `test_daily_demand.py`, `test_dashboard_app.py`; 90 full-day runs |
| 2. Riders request | Daily temporal/OD regimes plus independent request-probability thinning | Arrival-window, reversal and unchanged-opportunity thinning tests; request-arrived events |
| 3. System proposes prices | Firm rider total and distinct driver gross pay before acceptance; policy-specific OD incentives | `decisions.py`, `daily_marketplace.py`; recorded `price_proposed` events |
| 4. Probabilistic rider response | Shared logistic response to total quoted price, with keyed draw | Recovery/probability tests, quote-response event chain and preserved accepted-price tests |
| 5. Drivers choose between requests | Multinomial request menu and idle option, seeded rotating priority, one assignment per driver/request | Competing-menu integration test; full-day menus in all three policies; no duplicate assignments |
| 6. Adaptive spatial pricing | Bonus and rider adjustment use both trip ends' current shortage; new quotes respond as states change | Same-route controlled shortage reversal; synthetic morning/evening demand reversal; daily realized region histories |
| 7. Three policies | P0, P5, adaptive OD in UI and default CLI; legacy behavior requires historical configurations | Active-policy registry; UI option-count and default-config equality tests |
| 8. Representative visualization/KPIs | Demand/supply/shortage heatmaps, numeric legend, region curves, daily policy curves, revenue/wait/service/subsidy tables and paired uncertainty | Browser-rendered daily comparison and calibration panels; table alternatives; exported trajectories |
| 9. Shared assumptions | Identical request/fleet generation, behavior coefficients and keyed random draws across policies | Three-policy parity regression; 30 paired seeds with common inputs |
| 10. Calibration/tuning | Public-speed parameter fit with disjoint sites; deployable checksum-matched profile; rider-response fitting workflow; unsupported demand/driver coefficients labeled assumptions | `calibration.py`, two calibration scripts, recovery/rejection/application tests; `CALIBRATION.md`, public report and calibrated full-day network smoke |

## Evidence and interpretation

The software suite has 104 passing tests and 85% core-package statement coverage at the measured check. Ruff and diff checks pass. The full-day policy experiment consists of 90 runs; population, utilization and contribution identities reconcile. Integration tests also check reservation/settlement budgets at every epoch. The latest final-code test run and remote CI are recorded in the delivery update and PR.

The adaptive rule's controlled same-route quote changes from a CAD 7 bonus when the destination is relatively short to zero when that imbalance reverses. The 30-seed outcome study does not claim a winner: adaptive pricing increases modeled contribution while reducing completed service, and P5 lowers mean realized pickup wait. See `DAILY_RESULTS.md` and committed evidence for exact effects and intervals.

Road-speed calibration uses 23,284 mapped training rows across 801 sites. On 5,531 held-out mapped observations, MAE is 6.694 km/h versus free-flow 6.961 km/h. These are approximate spot speeds from a bounded sample; prior held-out sites are reused for exploratory evaluation. No acceptance threshold or marketplace validation claim follows. A full-day five-driver network run loads this profile and uses no straight-line fallback.

## Explicit limits beyond the functional objective

Rider/driver empirical behavior and demand remain assumptions under the user's data direction; no synthetic recovery fit is promoted to observed truth. Five-person formative usability testing and a full accessibility audit have not been performed. Larger network scalability, operating-cost modeling, congestion feedback and measured trip-time validation remain future research/release checks. These limitations are visible in the platform and documentation. Merge and public hosting remain separate actions.

The working dashboard is on port 8502; an older process occupies 8501. Browser review used the current source on 8502. Local generated outputs and large raw/network/profile artifacts are ignored by Git; compact evidence and reproducible scripts are committed for review in draft PR #1.
