# Daily marketplace: requests, quotes and driver choices

This workspace compares **three policies** using a shared 24-hour population and shared behavioral coefficients. The daily scenario is a synthetic stress test, not an observed Toronto operating day. Public road-speed observations inform the separate travel-cost evaluation; rider demand and price responses remain assumptions unless supported by suitable observations.

## The three policies

| Policy | Rider quote | Driver pay | Movement of idle drivers |
|---|---|---|---|
| Fixed-price baseline (P0) | Base fare | 75% of base fare | None |
| Repositioning (P5) | Base fare | 75% of base fare | Surplus-to-shortage reposition offers |
| Adaptive origin–destination pricing | Base fare plus bounded OD adjustment | 75% of base fare plus bounded destination bonus | Through paid occupied trips; no empty reposition intervention |

P5 retains its original meaning. The adaptive policy tests whether prices can encourage useful trips toward a shortage. The legacy eight-policy experiments remain readable by explicit legacy configurations, but are not the daily workspace's menu.

## One request's lifecycle

1. A seeded potential rider opportunity occurs at a sampled time. The shared request probability determines whether it becomes a request; this is separate from price acceptance.
2. At the next decision epoch, the system estimates the occupied route and proposes a **firm rider total price and driver gross payment**. An unreachable trip in network research has no quote and expires under the queue-wait rule.
3. The rider accepts with `sigmoid(rider_intercept − rider_price_per_cad × total_rider_price)`. Both functions and seeded draws are shared across policies. Different policy prices may correctly produce different probabilities.
4. Available drivers receive menus of currently available, rider-accepted requests. Choice weights are `exp(intercept + earnings_gain × gross_pay − pickup_penalty × pickup_minutes − occupied_penalty × occupied_minutes)`. Staying idle has weight 1. Normalize all weights together: drivers can prefer one request over another or reject the whole menu.
5. A seeded rotating driver priority resolves competition. A driver chooses once per epoch; an assigned request is removed before the next driver chooses. This prevents duplicate booking. Menu order does not affect probabilities. This is a sequential choice approximation, not simultaneous bargaining.
6. The driver travels to pickup, carries the rider, then becomes available at the destination. P5 may offer idle repositioning after trip matching. Accepted rider prices and driver pay stay fixed even if later route duration estimates change.

Decision events expose each price, origin/destination shortage, rider probability and draw, and driver menu probabilities. An outside-option choice is a rejected menu, not a rejection of every individual rider. Consequently the acceptance-rate denominator is driver menu decisions in the daily model; it must not be pooled with legacy per-offer rates.

## Origin–destination pricing

Let `I_o` and `I_d` be origin and destination waiting requests minus available drivers. Let `T = max(0, I_d − I_o)`. Defaults are:

- Rider adjustment: `clip(0.5 × I_o − 0.5 × T, −5, +5)` CAD.
- Driver bonus: `min(12, 1.0 × T)` CAD.
- Base fare: `3.50 + 1.10 × occupied_km + 0.35 × occupied_minutes` CAD.
- Driver gross payment: `0.75 × base_fare + bonus`.

Trips carrying supply from relative surplus into shortage earn a larger bonus; the direction reverses when shortages reverse. These are tunable rules, not an optimality or profitability guarantee. Shortages are measured at quote time; prices are not continually changed after rider acceptance. In-progress arrivals are not forecast into that signal.

The subsidy is the actual discount plus bonus. Before proposing a quote, the system checks the remaining budget after settled subsidies and existing commitments. It scales subsidies if necessary and floors rider payment at zero. Rider acceptance reserves the quote's subsidy; assignment transfers the same reservation to the movement; completion settles it. Price declines and queue cancellations release waiting reservations. Unfinished quotes/trips remain committed at the horizon and are reported separately.

## Dynamic daily demand

The default day is 00:00–24:00, 60 drivers, 1,200 potential opportunities, and a shared request probability of 0.8. Fixed-count opportunities sample hourly rates proportional to the values below; these are relative intensities, not observed counts or a Poisson process.

| Time | Synthetic regime | Relative intensity | OD emphasis |
|---|---|---:|---|
| 00–06 | Overnight | 0.25 | Central origins, distributed destinations |
| 06–10 | Morning inbound | 2.0 | Peripheral origins, central destinations |
| 10–16 | Midday distributed | 1.0 | Mixed locations |
| 16–20 | Evening outbound | 2.2 | Central origins, peripheral destinations |
| 20–24 | Night activity | 0.8 | Central destinations |

“Central” is the analytical rectangle south of 43.69 latitude and between −79.44 and −79.33 longitude, intersected with the study boundary. “North” is latitude at least 43.75; the remainder is split west/east at −79.40 longitude. These are scenario partitions, not official neighborhoods. Within regions, demo endpoints sample clipped H3 cells; network endpoints sample eligible road nodes. Supply changes through accepted trips and P5 repositioning. Drivers remain in the fleet all day; shifts are not modeled.

## Read the map and outcomes

The dark line is the Toronto study boundary. Hexagons are H3 resolution-8 analysis zones, clipped for display. Circles show waiting pickup locations; diamonds show requested destinations; driver symbols have state-specific colors and text tooltips. Solid paths follow roads; segmented paths are illustrative straight-line estimates. A persistent legend and searchable map-data table provide text alternatives.

Demand and supply layers show counts per cell, not population per square kilometre. Shortage is their difference. Price layers show mean adjustments/bonuses among quotes offered at each origin in the latest epoch; individual OD quotes may differ. The quote inspection panel is authoritative for trip prices. Arrival times in tooltips are minutes from midnight.

Completed trips require drop-off before the horizon. Waiting, cancelled, price-declined and in-progress trips are separate. Realized pickup wait covers riders actually collected; low wait among a small served group does not imply universal good service. Utilization uses elapsed pickup plus occupied time; empty reposition time is separate. Driver earnings are gross; platform contribution is rider payments minus driver gross payments, before operating costs. Curves show current waiting/in-progress populations and cumulative completions.

Compare paired seeds against P0, with the same requests, fleet, response coefficients and random streams. Thirty seeds is the research default; three is only a preview. Confidence intervals describe simulated variability and do not prove calibration. No policy is automatically declared the winner.

## Limits and calibration status

Traffic is external; simulated vehicles do not cause congestion. Travel costs are fixed within each departure-bucket leg. Demo uses straight-line speeds; network research excludes unreachable assignments. The public-data report concerns observed spot-speed bins only. It does not calibrate passenger arrivals, price elasticity, driver preferences or actual commercial fares. Suitable public data will be used where it supports the measurement; unsupported parameters remain labeled assumptions. The road-speed parameter fit and rider-response fitting workflow are documented in CALIBRATION.md. Full-day paired outcomes and their limitations are in DAILY_RESULTS.md.

## Shared tunable behavioral parameters

| Parameter | Default | Units / supported range | Evidence |
|---|---:|---|---|
| Request probability | 0.8 | Probability [0,1] per potential opportunity | Assumed |
| Rider acceptance intercept | 2.0 | Finite logit intercept | Assumed; fitting workflow available |
| Rider total-price coefficient | 0.08 | Per CAD, nonnegative | Assumed; fitting workflow available |
| Driver choice intercept | 0.5 | Finite utility intercept relative to idle | Assumed |
| Driver gross-pay coefficient | 0.10 | Per CAD, nonnegative | Assumed |
| Pickup burden coefficient | 0.18 | Per minute, nonnegative | Assumed |
| Occupied-time burden coefficient | 0.02 | Per minute, nonnegative | Assumed |
| Reposition acceptance | 0.7 | Probability [0,1] | Assumed; applies when repositioning is offered |

Changing these values applies the same response model to all active policies. Policy gains are separate design variables: origin price gain 0.5, destination-transfer bonus gain 1.0 and transfer-discount gain 0.5, all nonnegative. The maximum rider adjustment is CAD 5, maximum bonus CAD 12, and total subsidy budget CAD 500. These bounds apply before quotes are accepted. The service-rate denominator is actual requests arriving by the horizon, including price declines; potential opportunities that never request a ride are not in that denominator.
