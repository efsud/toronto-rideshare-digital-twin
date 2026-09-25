# Model handbook — v0.5 research prototype

This is a discrete, synthetic marketplace experiment on Toronto geography. It is not a forecast of Uber or Lyft operations. One rider party occupies a vehicle; pooling, endogenous congestion, operating expenses, reinforcement learning and SUMO integration are outside this release. Software correctness, empirical accuracy and human understanding are separate claims.

## How a run is developed

`ScenarioConfig` resolves defaults and validates a scenario. The same `create_engine` factory initializes the dashboard and CLI. It loads the optional directed road graph and traffic profile, defines H3 zones, generates potential requests and drivers, and initializes the clock. Every decision epoch processes movement completions up to that time, releases requests, expires excessive queue waits, computes zone imbalance, decides prices, matches drivers and requests, and proposes repositioning. The final epoch is clamped to the horizon. Movement positions change at endpoints, while elapsed busy time is integrated over each leg.

In illustrative mode, each request endpoint and driver location is sampled uniformly among analysis cells, then inside the selected cell's intersection with the boundary. This is uniform by cell, not by population or exactly by land area. In network mode, endpoints are sampled uniformly from eligible graph nodes within the boundary. Neither mode models observed neighborhood demand. Request times are uniform over the configured interval. The number of requests is `round(base_trip_count × demand_multiplier)`.

Demand, fleet and behavior have separate seeded streams. Shared behavior uses event-keyed draws, so unrelated policy branches do not consume each other's random numbers. Every policy sees the same potential requests and initial fleet for a given seed. Network-node placement has separate streams. Legacy v0.4 preserves the old policy-specific behavioral preset and sequential draws; it does not restore corrected defects or guarantee old numerical results.

## Roads and travel

OSM intersections/connectivity are directed graph nodes; road segments are directed keyed edges. For each edge, seconds = length metres / (speed km/h ÷ 3.6). Routing minimizes total seconds and retains the selected directed edge keys and oriented geographic geometry, including parallel edges.

Traffic costs use the nearest available departure bucket (07:00, 08:30, 12:00, 17:00). Costs remain fixed through the leg. Missing observations may use highway-class or citywide imputation, explicitly recorded in the profile; entirely missing buckets use free-flow costs. These are external traffic inputs: simulated fleet growth does not slow roads. Separate routing contexts cache weighted graph copies and routes without mutating the loaded graph.

**Illustrative demo:** no graph is required. Straight-line distance uses 30 km/h below 5 km and 25 km/h otherwise. Segmented map links identify these estimates. **Network research:** requires a graph; candidates without a reachable pickup or occupied route are excluded. A missing traffic profile permits free-flow network routing and is reported separately. The downloaded graph extent differs from the study boundary; routes can traverse roads beyond that boundary. No claim is made that every Toronto street is connected or covered.

## Prices, response and accounting

All amounts are CAD. Illustrative base fare is `3.50 + 1.10 × occupied kilometres + 0.35 × occupied minutes`. Rider payment is `max(0, base fare + adjustment)`. Driver gross earnings are `0.75 × base fare + bonus`. These fixed coefficients are displayed in setup; they are assumptions, not verified commercial tariffs. Vehicle expenses and platform operating costs are excluded.

Default driver acceptance is `sigmoid(0.5 + 0.10 × offered gross earnings − 0.18 × pickup minutes)`. Shared rider acceptance is `clip(1 − 0.3 × adjustment / 5, 0, 1)` where 5 CAD is the fixed response scale. Reposition acceptance is 0.7. The extra bonus-response multiplier is off by default because gross earnings already include the bonus. These response functions are assumed, not estimated from Toronto drivers or passengers. Discounts can retain generated potential requests, but cannot create customers outside that population.

Accepted assignments reserve the actual applied discount plus bonus against the subsidy budget. Completion settles the reserved amount; unfinished assignments retain commitments. Contribution equals settled rider payments minus settled driver gross earnings. “Revenue” and “earnings” fields in legacy JSON retain their keys for compatibility; the interface explains the corrected meanings.

## Policy comparison guide

| Policy | Rider adjustment | Driver bonus | Default matching | Reposition |
|---|---|---|---|---|
| P0 Fixed-price baseline | None | None | Greedy | No |
| P1 Rider pricing | Imbalance rule | None | Greedy | No |
| P2 Driver incentives | None | Imbalance rule | Greedy | No |
| P3 Two-sided rules | Rule | Rule | Greedy | No |
| P4 Optimized pricing and matching | LP | LP | Batch | No |
| P5 Repositioning | None | None | Greedy | Yes |
| P6 Rules plus repositioning | Rule | Rule | Greedy | Yes |
| P7 Optimization plus repositioning | LP | LP | Batch | Yes |

Imbalance is waiting demand minus idle supply. Rule adjustment is `clip(0.5 × imbalance, −5, 5)`; rule bonus is `min(max(imbalance, 0), 12)`, with configurable caps. The LP minimizes a linear response proxy under price, budget and cross-zone adjustment bounds. It does not directly minimize future realized wait or maximize actual profit. The cross-zone bound is not a demographic fairness guarantee. Solver/fallback evidence is retained in policy events and manifests.

Batch matching maximizes feasible assignment cardinality and then minimizes total pickup time. Its selected assignments reserve their drivers; a rejected selected offer waits for a subsequent epoch. Greedy matching considers nearest feasible drivers. Repositioning processes larger shortages first, reserves target capacity, avoids removing source supply below its waiting demand, and chooses feasible drivers by travel time.

Use the default 30 paired seeds and compare differences against P0 with Student-t 95% confidence intervals. Three seeds are a quick preview; one seed has unavailable uncertainty. Hold matching fixed in the controlled comparison to isolate pricing or repositioning. Otherwise P4/P7 change matching too. Overrides are custom variants. Higher policy numbers do not imply better outcomes. Intervals describe simulated variation, not calibration uncertainty or causal effects in Toronto.

## Map legend and boundary

The **Toronto study boundary** is a separate dark outline. The stored asset was derived from 25 City ward polygons, dissolved, repaired and simplified; metadata records retrieval on September 14, 2026. It is an analytical boundary, not a legal survey. The 823 **Analysis zones — H3 resolution 8** are computational cells, not wards or neighborhoods. Their centers define membership; displayed polygons are clipped while IDs remain unchanged.

| Mark | Meaning |
|---|---|
| Orange circle | Waiting pickup |
| Purple diamond | Requested destination |
| Driver symbol, green | Driver available |
| Driver symbol, amber | Driver heading to pickup |
| Driver symbol, blue | Driver carrying rider |
| Driver symbol, purple | Driver repositioning |
| Check / cross | Accepted / rejected offer — latest step |
| Solid path | Road-network route |
| Segmented path | Straight-line estimate — illustrative |

The active path is driver-to-pickup, pickup-to-drop-off, or reposition origin-to-target. Driver tooltips expose state, request, leg, ETA and routing source. Layer controls reduce clutter. Inspect an entity by map selection or the keyboard select box; search the equivalent table by ID or state. Zone color represents one selected quantity with units and a numeric scale; blue denotes negative, neutral zero, amber positive. Text and symbols supplement color. Map positions are not live GPS traces.

## Outcomes and denominators

- **Completed:** drop-off by processed time (the horizon for final reports).
- **In progress:** accepted but unfinished. **Waiting:** arrived and unassigned.
- **Cancelled:** unassigned queue wait exceeds the configured maximum. This does not cap queue-plus-pickup time.
- **Price declined:** potential request rejected the offered price. **Future:** not yet released.
- **Service rate:** completed / arrived potential requests, including price-declined and cancelled demand in the denominator.
- **Realized pickup wait:** request-to-pickup time, only riders actually collected. **Mean pickup time:** driver-to-pickup duration for collected riders. **Mean trip time:** occupied duration for completed trips.
- **Utilization:** elapsed pickup plus occupied minutes / elapsed fleet minutes. Reposition minutes are separate. Future booked travel is never counted as elapsed utilization.
- Planned duration totals remain available separately from realized totals. Request-state totals and settled payment identities must reconcile.

## Parameter reference

Defaults below are resolved by `scenario.py`. UI bounds are narrower convenience ranges; valid YAML/JSON can use the mathematical ranges below. Time is Toronto local time within one same-day interval. All numeric coefficients must be finite. Unless stated otherwise, sources are explicit model assumptions.

| Parameter | Default | Units / range | Scope |
|---|---|---|---|
| Start / end | 07:00 / 10:00 | HH:MM, end ≥ start | All |
| Decision interval | 5 | minutes, >0 | All |
| Fleet | 20 | integer ≥0 | All |
| Base potential requests | 20 | integer ≥0 | All |
| Demand multiplier | 1 | ≥0 | All |
| Maximum unassigned queue wait | 15 | minutes, >0 | All |
| Seed | 42 | integer ≥0 | All |
| Routing | demo | demo / network_research | All |
| Behavior | shared | shared / legacy_v0.4 | All |
| Matching | policy_default | policy_default / greedy / optimal_batch | All |
| Rider adjustment cap | 5 | CAD ≥0 | P1/P3/P4/P6/P7 |
| Driver bonus cap | 12 | CAD ≥0 | P2/P3/P4/P6/P7 |
| Subsidy budget | 500 | CAD ≥0 | Subsidized assignments |
| Cross-zone adjustment difference | 3 | CAD ≥0 | LP policies |
| Rider price response | −0.3 | coefficient ≤0 | Rider-adjustment policies |
| Extra bonus response | 0.4, disabled | coefficient ≥0 | Bonus policies if enabled |
| Reposition acceptance | 0.7 | probability [0,1] | P5/P6/P7 |
| Driver logistic intercept | 0.5 | finite coefficient | All |
| Driver earnings response | 0.10 | per CAD ≥0 | All |
| Driver pickup penalty | 0.18 | per minute ≥0 | All |
| LP demand / supply response | 0.06 / 0.04 | per CAD ≥0 | P4/P7 proxy only |
| Graph / traffic paths | data/processed defaults | existing files for requested use | Network |

## Provenance and trust

Versioned manifests contain the resolved scenario, code commit and dirty state, dataset checksums, seed streams, solver/fallback evidence, routing counts and metric definitions. The graph saver records acquisition metadata and connectivity. Keep legacy results separately; do not pool them silently with v0.5 results. A matching checksum does not establish accuracy.

Validation status is **Not evaluated**, **Insufficient data**, **Compared with observed data**, or **Meets stated benchmark criteria** only when explicit documented criteria exist. Empty comparisons never pass. The supplied tiny traffic CSV is a synthetic software fixture. The public speed report is separate evidence and does not validate requests, driver acceptance, fares or earnings. A five-participant formative study remains necessary to assess human understanding; automated browser checks cannot replace it.
