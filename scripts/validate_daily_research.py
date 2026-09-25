"""Reproduce paired full-day policy effects and an explicit shortage-reversal check."""

import json
import time
from pathlib import Path

from toronto_rideshare.demand.models import TripRequest
from toronto_rideshare.experiments.runner import run_repeated_policy_comparison
from toronto_rideshare.manifest import file_checksum
from toronto_rideshare.policies.registry import POLICY_REGISTRY, PolicyId
from toronto_rideshare.simulation import SimulationClock, SimulationEngine
from toronto_rideshare.supply.models import Driver
from toronto_rideshare.zones import lat_lon_to_zone


def reversal_evidence():
    a, b = (43.65, -79.38), (43.70, -79.45)
    za, zb = lat_lon_to_zone(*a), lat_lon_to_zone(*b)
    records = []
    # Controlled market states isolate the same A→B trip from confounding route changes.
    # These are two scenario snapshots, not a claim of causal field validation.
    for minute, supply_at, demand_at in ((480, a, b), (1080, b, a)):
        supply_zone, demand_zone = lat_lon_to_zone(*supply_at), lat_lon_to_zone(*demand_at)
        target = TripRequest("target", minute, *a, *b, za, zb)
        queue = [target] + [
            TripRequest(f"other{i}", minute, *demand_at, *a, demand_zone, za) for i in range(4)
        ]
        engine = SimulationEngine(
            SimulationClock(minute, minute, 5),
            [Driver(f"D{i}", *supply_at, supply_zone) for i in range(4)],
            queue,
            policy_settings=POLICY_REGISTRY[PolicyId.ADAPTIVE],
            marketplace_model="driver_choice",
            behavior_profile="shared",
            daily_behavior={"rider_intercept": 40},
            policy_cfg={"subsidy_budget_cad": 1000},
        )
        engine.step()
        proposal = next(
            e
            for e in engine.events
            if e["type"] == "price_proposed" and e["request_id"] == "target"
        )
        records.append({"minute": minute, "quote": proposal["quote"]})
    first, second = [r["quote"] for r in records]
    assert first["transfer_value"] > 0 > second["transfer_value"]
    assert first["fare"]["driver_bonus_cad"] > second["fare"]["driver_bonus_cad"]
    assert first["fare"]["rider_payment_cad"] < second["fare"]["rider_payment_cad"]
    return {
        "status": "software_response_verified",
        "scope": "controlled market-state reversal",
        "same_route": True,
        "snapshots": records,
        "limitation": "Not an empirical test and not evidence of improved system outcomes",
    }


def main():
    out = Path("results/daily_research")
    out.mkdir(parents=True, exist_ok=True)
    start = time.perf_counter()
    comparison = run_repeated_policy_comparison(
        "configs/experiments/full_day.yaml", n_replicates=30
    )
    comparison["runtime_seconds"] = time.perf_counter() - start
    for row in comparison["replicates"]:
        m = row["metrics"]
        assert (
            m["completed_trips"] + m["in_progress_trips"] + m["unserved_trips"]
            == row["generated_trip_count"]
        )
        assert 0 <= m["utilization_rate"] <= 1
        assert (
            abs(
                m["total_rider_payment_cad"]
                - m["total_driver_earnings_cad"]
                - m["platform_net_revenue_cad"]
            )
            < 1e-7
        )
    full = out / "paired_30_seeds.json"
    full.write_text(json.dumps(comparison, indent=2))
    summary = {k: v for k, v in comparison.items() if k not in ("replicates", "config_path")}
    summary["replicate_count"] = len(comparison["replicates"])
    summary["resolved_scenario"] = comparison["replicates"][0]["manifest"]["scenario"]
    summary["full_result_sha256"] = file_checksum(full)
    summary["reversal_check"] = reversal_evidence()
    (out / "summary.json").write_text(json.dumps(summary, indent=2))
    print(
        json.dumps(
            {
                "runs": len(comparison["replicates"]),
                "seconds": comparison["runtime_seconds"],
                "reversal": summary["reversal_check"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
