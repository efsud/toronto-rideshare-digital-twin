# Release readiness — v0.5 research prototype

Prepared September 24, 2026. The implementation is reviewable; it is not a blanket validated-platform release. Draft PR #1 remains the delivery vehicle. Merging and hosting are separate actions.

| Area | Evidence | Status / remaining work |
|---|---|---|
| Unified scenario | Same factory in dashboard and runner; input rejection and parity tests | Implemented |
| Model correctness | Traffic parsing, assignment reservations, empty validation rejection, horizon and elapsed utilization regressions | Implemented |
| Geography/routing | Constrained sampling, clipped zones, active-leg geometry, strict no-path behavior, immutable costs | Implemented |
| Policies/experiments | Shared/keyed behavior, reserved subsidy accounting, capacity-aware reposition, P0 paired Student-t comparisons | Implemented |
| Workspace | Four guided views, pending/apply/reset, labels, map legend, symbols, table alternative and JSON exports | Implemented; formative usability pending |
| Software checks | 87 tests passed; 84% core-package statement coverage; Ruff passed | Local Python environment; CI checked separately on PR |
| Actual browser | Chrome at 1440 px and 390 px, no page errors or horizontal overflow in reviewed flows | Visual review, not WCAG conformance certification |
| Public speeds | 42,281 usable rows; site holdout; matched speed MAE 6.792 km/h | Compared with observed data; no pass threshold |
| Human understanding | Five-task protocol and results template provided | No participants tested; required before usability sign-off |
| Deployment | Local Streamlit available | Public hosting out of scope |

## Performance and reproducibility

The demo benchmark ran 20/100/200 drivers with matching request counts in approximately 0.20/0.47/1.04 seconds on this machine; peak traced Python allocations were approximately 3.43/2.80/3.06 MB. These are neither total RSS nor network-mode performance limits. A 30-seed, eight-policy demo comparison (240 runs) took about 25 seconds. Evidence includes all paired estimates; no winning policy is declared. Full manifests remain in the local generated results; committed summaries preserve the scenario, seeds and source file checksum.

A full-Toronto five-driver network smoke run took about 19.6 seconds including loading/preparation. Larger network scenarios need dedicated runtime and total-memory profiling before a supported-scale claim. The graph is about 73,000 directed edges and most speed costs are imputed.

## Explicit release gaps

1. Conduct the five-participant study in `USABILITY_PROTOCOL.md`, revise observed failures and retest. No simulated user findings have been invented.
2. Complete keyboard/screen-reader and contrast review against WCAG 2.2, especially WebGL selection. The searchable table and select box provide text alternatives but do not establish conformance.
3. Expand representative public sampling and establish documented empirical acceptance criteria. Validate trip times separately from spot speeds.
4. Obtain appropriate empirical demand and behavioral observations before claiming a calibrated marketplace. Present gross earnings and contribution as assumed-model outputs.
5. Profile 20/100/200-driver network scenarios and process RSS before expanding network support; demo results cannot establish network scalability.

Legacy documents and DOCX describe older development stages and remain historical. The model handbook, public report and resolved manifests govern this release's interpretation. The legacy behavior preset retains earlier behavioral differences only, not old defects. Review solver fallback metadata and avoid combining model versions silently.
