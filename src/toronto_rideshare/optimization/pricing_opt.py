"""OR-Tools LP for zone-level rider/driver adjustments."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PricingDecision:
    zone: str
    rider_adjustment_cad: float
    driver_bonus_cad: float
    predicted_demand_change: float = 0.0
    predicted_supply_change: float = 0.0
    expected_subsidy_cad: float = 0.0
    expected_incremental_revenue_cad: float = 0.0
    backend: str = "heuristic"


def _heuristic_fallback(
    zone_imbalance: dict[str, dict[str, float]],
    *,
    rider_cap: float,
    bonus_cap: float,
    total_budget_cad: float,
    fairness_bound_cad: float,
) -> list[PricingDecision]:
    from toronto_rideshare.policies.incentives import driver_bonus_cad
    from toronto_rideshare.policies.pricing import rider_adjustment_cad

    raw = {
        zone: [
            rider_adjustment_cad(float(stats["imbalance"]), cap=rider_cap),
            driver_bonus_cad(float(stats["imbalance"]), cap=bonus_cap),
        ]
        for zone, stats in sorted(zone_imbalance.items())
    }
    for index in (0, 1):
        values = [value[index] for value in raw.values()]
        if max(values) - min(values) > fairness_bound_cad:
            midpoint = (max(values) + min(values)) / 2.0
            low = midpoint - fairness_bound_cad / 2.0
            high = midpoint + fairness_bound_cad / 2.0
            for value in raw.values():
                value[index] = max(low, min(high, value[index]))

    total_subsidy = sum(
        max(1.0, float(zone_imbalance[zone].get("demand", 1.0)))
        * (max(0.0, -values[0]) + values[1])
        for zone, values in raw.items()
    )
    scale = min(1.0, max(0.0, total_budget_cad) / total_subsidy) if total_subsidy else 1.0
    decisions: list[PricingDecision] = []
    for zone, stats in sorted(zone_imbalance.items()):
        rider, bonus = raw[zone]
        if rider < 0.0:
            rider *= scale
        bonus *= scale
        demand = max(1.0, float(stats.get("demand", 1.0)))
        subsidy = demand * (max(0.0, -rider) + bonus)
        decisions.append(
            PricingDecision(
                zone=zone,
                rider_adjustment_cad=rider,
                driver_bonus_cad=bonus,
                predicted_demand_change=-0.06 * demand * rider,
                predicted_supply_change=0.04 * max(1.0, float(stats.get("supply", 1.0))) * bonus,
                expected_subsidy_cad=subsidy,
                expected_incremental_revenue_cad=demand * max(0.0, rider),
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
    fairness_bound_cad: float = 3.0,
    demand_response_per_cad: float = 0.06,
    supply_response_per_cad: float = 0.04,
) -> list[PricingDecision]:
    """Optimize documented linear demand/supply response within fiscal bounds.

    Budget pays only rider discounts and driver bonuses. Positive rider
    adjustments are revenue, not negative subsidy. Pairwise fairness bounds
    constrain differences in rider adjustments and bonuses between zones.
    """
    if not zone_imbalance:
        return []

    try:
        from ortools.linear_solver import pywraplp
    except ImportError:
        return _heuristic_fallback(
            zone_imbalance,
            rider_cap=rider_cap,
            bonus_cap=bonus_cap,
            total_budget_cad=total_budget_cad,
            fairness_bound_cad=fairness_bound_cad,
        )

    solver = pywraplp.Solver.CreateSolver("GLOP")
    if solver is None:
        return _heuristic_fallback(
            zone_imbalance,
            rider_cap=rider_cap,
            bonus_cap=bonus_cap,
            total_budget_cad=total_budget_cad,
            fairness_bound_cad=fairness_bound_cad,
        )

    zones = sorted(zone_imbalance.keys())
    rider_vars: dict[str, pywraplp.Variable] = {}
    bonus_vars: dict[str, pywraplp.Variable] = {}
    discount_vars: dict[str, pywraplp.Variable] = {}

    for zone in zones:
        rider_vars[zone] = solver.NumVar(-rider_cap, rider_cap, f"rider_{zone}")
        bonus_vars[zone] = solver.NumVar(0.0, bonus_cap, f"bonus_{zone}")
        discount_vars[zone] = solver.NumVar(0.0, rider_cap, f"discount_{zone}")
        solver.Add(discount_vars[zone] >= -rider_vars[zone])

    objective = solver.Objective()
    for zone in zones:
        imb = float(zone_imbalance[zone]["imbalance"])
        demand = max(1.0, float(zone_imbalance[zone].get("demand", 1.0)))
        supply = max(1.0, float(zone_imbalance[zone].get("supply", 1.0)))
        objective.SetCoefficient(
            rider_vars[zone], rider_weight * imb * demand_response_per_cad * demand
        )
        objective.SetCoefficient(
            bonus_vars[zone], bonus_weight * imb * supply_response_per_cad * supply
        )
        objective.SetCoefficient(discount_vars[zone], -1e-9)
    objective.SetMaximization()

    budget = solver.Constraint(0.0, max(0.0, total_budget_cad))
    for zone in zones:
        demand = max(1.0, float(zone_imbalance[zone].get("demand", 1.0)))
        budget.SetCoefficient(discount_vars[zone], demand)
        budget.SetCoefficient(bonus_vars[zone], demand)

    for index, zone in enumerate(zones):
        for other in zones[index + 1 :]:
            solver.Add(rider_vars[zone] - rider_vars[other] <= fairness_bound_cad)
            solver.Add(rider_vars[other] - rider_vars[zone] <= fairness_bound_cad)
            solver.Add(bonus_vars[zone] - bonus_vars[other] <= fairness_bound_cad)
            solver.Add(bonus_vars[other] - bonus_vars[zone] <= fairness_bound_cad)

    status = solver.Solve()
    if status != pywraplp.Solver.OPTIMAL:
        return _heuristic_fallback(
            zone_imbalance,
            rider_cap=rider_cap,
            bonus_cap=bonus_cap,
            total_budget_cad=total_budget_cad,
            fairness_bound_cad=fairness_bound_cad,
        )

    return [
        PricingDecision(
            zone=zone,
            rider_adjustment_cad=rider_vars[zone].solution_value(),
            driver_bonus_cad=bonus_vars[zone].solution_value(),
            predicted_demand_change=(
                -demand_response_per_cad
                * max(1.0, float(zone_imbalance[zone].get("demand", 1.0)))
                * rider_vars[zone].solution_value()
            ),
            predicted_supply_change=(
                supply_response_per_cad
                * max(1.0, float(zone_imbalance[zone].get("supply", 1.0)))
                * bonus_vars[zone].solution_value()
            ),
            expected_subsidy_cad=(
                max(1.0, float(zone_imbalance[zone].get("demand", 1.0)))
                * (
                    discount_vars[zone].solution_value()
                    + bonus_vars[zone].solution_value()
                )
            ),
            expected_incremental_revenue_cad=(
                max(1.0, float(zone_imbalance[zone].get("demand", 1.0)))
                * max(0.0, rider_vars[zone].solution_value())
            ),
            backend="ortools-glop",
        )
        for zone in zones
    ]
