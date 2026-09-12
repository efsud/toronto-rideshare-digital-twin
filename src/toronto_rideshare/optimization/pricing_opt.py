"""OR-Tools LP for zone-level rider/driver adjustments."""

from __future__ import annotations

from dataclasses import dataclass

from toronto_rideshare.policies.incentives import driver_bonus_cad
from toronto_rideshare.policies.pricing import rider_adjustment_cad


@dataclass(frozen=True, slots=True)
class PricingDecision:
    zone: str
    rider_adjustment_cad: float
    driver_bonus_cad: float


def _heuristic_fallback(
    zone_imbalance: dict[str, dict[str, float]],
    *,
    rider_cap: float,
    bonus_cap: float,
) -> list[PricingDecision]:
    decisions: list[PricingDecision] = []
    for zone, stats in zone_imbalance.items():
        imb = float(stats["imbalance"])
        decisions.append(
            PricingDecision(
                zone=zone,
                rider_adjustment_cad=rider_adjustment_cad(imb, cap=rider_cap),
                driver_bonus_cad=driver_bonus_cad(imb, cap=bonus_cap),
            )
        )
    return decisions


def optimize_zone_pricing(
    zone_imbalance: dict[str, dict[str, float]],
    *,
    rider_cap: float = 5.0,
    bonus_cap: float = 12.0,
    total_budget_cad: float = 500.0,
    rider_weight: float = 1.0,
    bonus_weight: float = 1.0,
) -> list[PricingDecision]:
    """Solve LP: maximize incentive response to imbalance within budget caps.

    Falls back to rule-based heuristics if OR-Tools is unavailable.
    """
    if not zone_imbalance:
        return []

    try:
        from ortools.linear_solver import pywraplp
    except ImportError:
        return _heuristic_fallback(
            zone_imbalance, rider_cap=rider_cap, bonus_cap=bonus_cap
        )

    solver = pywraplp.Solver.CreateSolver("GLOP")
    if solver is None:
        return _heuristic_fallback(
            zone_imbalance, rider_cap=rider_cap, bonus_cap=bonus_cap
        )

    zones = sorted(zone_imbalance.keys())
    rider_vars: dict[str, pywraplp.Variable] = {}
    bonus_vars: dict[str, pywraplp.Variable] = {}

    for zone in zones:
        rider_vars[zone] = solver.NumVar(-rider_cap, rider_cap, f"rider_{zone}")
        bonus_vars[zone] = solver.NumVar(0.0, bonus_cap, f"bonus_{zone}")

    objective = solver.Objective()
    for zone in zones:
        imb = float(zone_imbalance[zone]["imbalance"])
        objective.SetCoefficient(rider_vars[zone], rider_weight * imb)
        objective.SetCoefficient(bonus_vars[zone], bonus_weight * imb)
    objective.SetMaximization()

    budget = solver.Constraint(0.0, total_budget_cad)
    for zone in zones:
        budget.SetCoefficient(rider_vars[zone], 1.0)
        budget.SetCoefficient(bonus_vars[zone], 1.0)

    status = solver.Solve()
    if status != pywraplp.Solver.OPTIMAL:
        return _heuristic_fallback(
            zone_imbalance, rider_cap=rider_cap, bonus_cap=bonus_cap
        )

    return [
        PricingDecision(
            zone=zone,
            rider_adjustment_cad=rider_vars[zone].solution_value(),
            driver_bonus_cad=bonus_vars[zone].solution_value(),
        )
        for zone in zones
    ]
