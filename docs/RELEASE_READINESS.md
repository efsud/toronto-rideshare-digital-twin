# Daily marketplace readiness — v0.6 development

Updated September 25, 2026. This is a reviewable research prototype; merging and public hosting are separate release actions. Current tests pass locally; final remote CI status is reported on draft PR #1.

| Requirement | Evidence |
|---|---|
| Legend and meaningful map | Persistent boundary/zone/agent/route legend; separate demand/supply counts, shortage and quote means; searchable text table; Chrome visual review |
| At least one day | Default 00:00–24:00 scenario; horizon test; full-day button and actual browser completion |
| Requests | Independent potential-request probability; daily arrival/OD regimes; deterministic thinning tests |
| Rider/driver price proposals | Immutable trip quote, subsidy cap before rider response, distinct rider payment and driver gross pay; inspectable events |
| Rider price response | Shared total-price logistic response and keyed draws; acceptance/rejection events |
| Driver request choice | Multinomial menu choice with idle outside option; rotating keyed priority; unique assignment tests |
| Adaptive OD mechanism | Destination-minus-origin shortage incentives; morning/evening synthetic flow reversal; controlled same-route reversal evidence |
| At most three active policies | P0, P5 and adaptive OD in dashboard/default daily comparisons; historical configurations remain readable |
| KPI and temporal comparison | Current heatmaps, regional demand/supply curves, hourly policy trajectories, paired effects and intervals |
| Common assumptions | Exact input/fleet/behavior/draw parity tests; 30 paired seeds, 90 complete-day runs |
| Calibration | Public-speed parameter fit with site holdout and checksum-verified application; rider-response fitting workflow with synthetic recovery tests; unsupported behavior/demand explicitly assumed |

The core software suite has 104 passing tests (85% core-package coverage). The 90-run experiment reconciles all request states, utilization and payment identities. Full-day integration checks conserve settled plus committed subsidies at every step. Chrome review covers desktop/narrow layouts and actual daily completion, comparison charts and calibration panel. A full-day five-driver network check also uses the fitted profile without straight-line fallback; this is integration evidence, not a supported-scale benchmark.

The policy experiment uses illustrative demo routing, not the calibrated network. Under its assumptions, adaptive pricing increases platform contribution while reducing completed service; P5 reduces realized pickup wait. Read `DAILY_RESULTS.md` for exact effects and uncertainty. No winner is declared.

## Remaining research and release limits

- Road calibration targets approximate spot-speed bins in a bounded nonrepresentative sample. No predeclared benchmark or independent measured trip-time validation exists. Demand, acceptance coefficients, initial fleet and commercial fares remain assumptions.
- Five representative humans have not completed the formative usability protocol. Automated browser review does not replace that study, screen-reader review or a WCAG conformance audit.
- Larger network scenarios require process-memory/runtime profiling before any supported-scale claim. Demo speed does not establish network scalability.
- Congestion is external, positions move at endpoints, and driver work shifts are absent. Synthetic scenario regions are not official neighborhoods. Sequential choice is an approximation to competing-driver decisions.
- Legacy outputs describe different behavioral and accounting models. Preserve their manifests and never pool them silently with the daily marketplace.

Public hosting, merging, SUMO, pooled trips and reinforcement learning are outside this release. The user requested public data where suitable and explicit assumptions where no suitable data are available; this distinction is maintained throughout the model and calibration views.
