# SUMO / TraCI Integration (Task 34 — Future)

SUMO is **not** implemented yet. The Python marketplace simulator must be validated first.

Planned integration:

1. Export matched trips and driver routes to SUMO routes.
2. Use TraCI to update edge travel times from SUMO feedback.
3. Compare Python-level tau_e(t) vs microsimulation congestion.

Do not replace the marketplace architecture with SUMO; use it as a validation layer.
