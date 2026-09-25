# Active full-day adaptive marketplace objective

This document tracks the September 25 request. It supersedes the earlier eight-policy product direction. Completion requires all items below, not just the existing software test suite.

## Target and assumptions

The user-facing workspace will offer three policies: fixed-price baseline, P5 repositioning, and adaptive origin–destination pricing. Historic policy IDs may remain readable for old results but should not expand the active comparison menu. Shared request-generation and acceptance functions, coefficients and event-keyed random draws apply to all three. Prices differ by policy; acceptance probabilities can therefore differ as a consequence of prices, not because the behavior model changed.

The daily scenario is a synthetic stress test: central/peripheral flows reverse over time. Geographic regions are analytical partitions, not official neighborhoods. No observed commuter pattern or empirical calibration is implied. A day means 00:00 through 24:00, with explicit unfinished rides at the horizon.

## Requirement evidence and remaining work

| User requirement | Current evidence | Remaining |
|---|---|---|
| 0. Map legend | Existing persistent labels and symbols | Recheck new layers in browser |
| 1. At least one day | 24:00 parser, full_day.yaml, complete-day run | Browser review of full-day controls |
| 2. Requests | Daily weighted arrival and OD sampling; independent request-probability thinning | Explain arrival and request stages in UI |
| 3–4. Price proposal then rider acceptance | Existing origin adjustment only | Store actual rider quote, show proposal/acceptance, honor accepted price |
| 5. Drivers choose among requests | Existing request-first offers | Competing-request choice with outside option, shared utility and conflict handling |
| 6. Adaptive origin–destination incentives | Daily synthetic regimes implemented | Implement destination-shortage pricing and verify reversal response |
| 7. At most three policies incl. P5 | Existing eight policies | Restrict workspace and default comparisons to target three |
| 8. Heatmaps and comparable KPIs | Existing demand/supply heatmaps and aggregate comparisons | Daily trajectories, OD price explanations and final browser review |
| 9. Shared assumptions | Split streams, common factory, daily input parity test | Choice/quote fairness tests across all target policies |
| 10. Calibration | Traffic speed evaluation exists | Fit behavior/demand parameters to supplied observations or targets with holdout; synthetic recovery check; honest data status |

## September 25 foundation evidence

91 tests pass, including new checks for day endpoint, peak arrival rates, morning/evening OD reversal, independent request thinning and identical daily P0/P5 inputs. A 60-driver day with 1,200 potential opportunities and request probability 0.8 produced 963 requests: 801 completed, 152 unserved, 10 in progress at midnight. State totals reconcile; utilization remains within [0,1]. These numbers exercise the existing matching/behavior path and are not yet evidence for the requested driver-choice or adaptive-pricing mechanism. Local report: `results/full_day_foundation.json`.

Keep the goal active until every requirement is implemented and verified. Calibration to real marketplace behavior cannot be claimed from public road-speed measurements alone.

## Decision-function groundwork

`marketplace/decisions.py` now defines immutable trip quotes, destination-minus-origin shortage incentives, subsidy capping before rider acceptance, total-price rider response, and multinomial driver choice among requests plus an idle outside option. Unit tests verify incentive reversal, budget conservation and comparative choice probabilities. These functions are not yet wired into the simulation's assignment loop; that integration must replace request-first offers in the target three-policy experience. The full current suite passes 95 tests. Version is marked 0.6.0.dev0 because the model is changing.

Calibration direction confirmed by the user: use suitable public data and label remaining assumptions. Public road speeds can support travel-cost fitting; they cannot establish rider/driver price responses.

Next integration steps: introduce the adaptive policy and three-policy menu; reserve a quote when proposed, store accepted rider prices, release reservations on decline/cancellation; build per-driver feasible menus; use common keyed choices and deterministic conflict resolution; connect chosen assignments to existing movement accounting; expose quote/choice event details and daily KPI/zone trajectories; add calibration fitting/holdout workflow and end-to-end reversal experiments.

## Integrated daily marketplace — September 25 continuation

The previous turn made concrete progress (committed daily-demand foundations). This turn integrates the firm quote and competing-request choice functions into `simulation/daily_marketplace.py`. The default dashboard now loads the 24-hour scenario and exposes exactly P0, P5 and adaptive OD pricing. Historical configurations retain the legacy offer engine for reproducibility.

Implemented: pre-acceptance budget capping, accepted quote retention, cancellation reservation release, seeded rotating driver priority with an idle outside option, unique assignments, actual movement settlement, per-epoch history, hourly exported trajectories, and inspectable decision menus. The shared-state regression covers all three policies. Current tests: 98 passing; Ruff and diff checks pass. Seven targeted UI/decision tests were rerun after display changes.

A full day under each policy used the identical 963 requests. Driver menus containing competing requests numbered 1,216 / 1,180 / 1,068 for P0 / P5 / adaptive respectively; P5 made 31 reposition movements. All three reconciled request populations and checked subsidy commitments plus settlement against the budget at every step. These are single-seed integration checks, not evidence that one policy performs better. Local report: `results/daily_three_policy_integration.json`.

Chrome review on the current dashboard at port 8502 confirms full-day completion, the three-policy menu and persistent map legend. Desktop and 390-pixel views had no page errors or horizontal overflow in checked flows. The older process occupying 8501 did not have the new full-day button; it was not treated as current evidence.

Still required before goal completion: calibration workflow using suitable public data with honest unsupported assumptions; controlled time-reversal experiments demonstrating adaptive mechanism response, paired full-day policy outcomes/uncertainty; richer temporal zone diagnostics and comparison curves; refresh documentation/release evidence, push reviewed changes to draft PR #1, verify CI, and perform the final requirement-by-requirement audit. The goal remains active.
