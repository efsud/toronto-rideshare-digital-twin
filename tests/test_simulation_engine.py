import json

from toronto_rideshare.demand import generate_trips
from toronto_rideshare.demand.models import TripRequest
from toronto_rideshare.policies.behavior import BehaviorConfig, OfferAcceptanceConfig
from toronto_rideshare.policies.registry import POLICY_REGISTRY, PolicyId, PolicySettings
from toronto_rideshare.simulation import SimulationClock, SimulationEngine
from toronto_rideshare.supply import initialize_fleet
from toronto_rideshare.supply.models import Driver, DriverStatus
from toronto_rideshare.zones import lat_lon_to_zone, toronto_zone_cells, zone_center


def test_simulation_engine_completes_trips() -> None:
    zone = lat_lon_to_zone(43.65, -79.38)
    trips = generate_trips([zone], n_trips=3, random_seed=0)
    drivers = initialize_fleet([zone], fleet_size=3, random_seed=0)
    clock = SimulationClock(end_time_min=200.0, step_min=5.0)
    engine = SimulationEngine(clock=clock, drivers=drivers, trips=trips)
    metrics = engine.run()
    assert metrics.completed_trips >= 1
    assert metrics.total_offers == metrics.accepted_offers + metrics.rejected_offers
    assert metrics.platform_net_revenue_cad == (
        metrics.total_rider_payment_cad - metrics.total_driver_earnings_cad
    )
    assert 0.0 <= metrics.acceptance_rate <= 1.0
    assert 0.0 <= metrics.service_rate <= 1.0
    json.dumps(engine.last_snapshot)


def _fallback_engine() -> SimulationEngine:
    zone = toronto_zone_cells()[100]
    lat, lon = zone_center(zone)
    destination = toronto_zone_cells()[101]
    dest_lat, dest_lon = zone_center(destination)
    trip = TripRequest("R1", 0.0, lat, lon, dest_lat, dest_lon, zone, destination)
    drivers = [
        Driver("D0", lat, lon, zone),
        Driver("D1", lat + 0.001, lon, zone),
    ]
    return SimulationEngine(
        clock=SimulationClock(end_time_min=5.0, step_min=5.0),
        drivers=drivers,
        trips=[trip],
        acceptance=OfferAcceptanceConfig(
            intercept=0.0, earnings_per_cad=0.0, pickup_minutes_penalty=0.0
        ),
        random_seed=10,  # draws 0.571 (reject), then 0.429 (accept)
    )


def test_step_rejection_falls_back_to_next_driver() -> None:
    engine = _fallback_engine()
    snapshot = engine.step()
    offers = [event for event in snapshot["events"] if event["type"].startswith("offer_")]
    assert [(event["type"], event["driver_id"]) for event in offers] == [
        ("offer_rejected", "D0"),
        ("offer_accepted", "D1"),
    ]
    assert snapshot["metrics"]["rejected_offers"] == 1
    assert snapshot["metrics"]["assigned_trips"] == 1
    assert snapshot["metrics"]["completed_trips"] == 0
    assert engine.drivers[1].status == DriverStatus.EN_ROUTE_PICKUP


def test_step_progression_and_reset_are_deterministic() -> None:
    engine = _fallback_engine()
    first = engine.step()
    assert first["time_min"] == 5.0
    assert not first["finished"]
    second = engine.step()
    assert second["finished"]
    reset = engine.reset()
    replay = engine.step()
    assert reset["time_min"] == 0.0
    assert replay["events"] == first["events"]


def test_run_and_steps_produce_same_metrics() -> None:
    run_engine = _fallback_engine()
    step_engine = _fallback_engine()
    run_metrics = run_engine.run()
    while not step_engine.finished:
        step_engine.step()
    assert run_metrics == step_engine.metrics


def test_explicit_movement_phases_complete_at_endpoints() -> None:
    engine = _fallback_engine()
    engine.clock.end_time_min = 30.0
    engine.clock.step_min = 0.25
    first = engine.step()
    movement = first["active_movements"][0]
    driver = next(d for d in engine.drivers if d.driver_id == movement["driver_id"])
    assert movement["phase"] == "en_route_pickup"
    assert [driver.lat, driver.lon] == movement["start"]

    phases = {driver.status}
    while not engine.finished:
        engine.step()
        phases.add(driver.status)
    assert DriverStatus.WITH_RIDER in phases
    assert engine.metrics.completed_trips == 1


def test_horizon_separates_arrived_from_future_requests() -> None:
    zone = toronto_zone_cells()[100]
    lat, lon = zone_center(zone)
    arrived = TripRequest("arrived", 0.0, lat, lon, lat, lon, zone, zone)
    future = TripRequest("future", 20.0, lat, lon, lat, lon, zone, zone)
    engine = SimulationEngine(
        clock=SimulationClock(end_time_min=5.0, step_min=5.0),
        drivers=[],
        trips=[arrived, future],
        max_wait_time_min=100.0,
    )
    engine.run()
    assert engine.metrics.unserved_arrived_trips == 1
    assert engine.metrics.not_yet_released_trips == 1
    assert engine.metrics.unserved_trips == 1


def test_max_wait_cancellation_emits_event() -> None:
    zone = toronto_zone_cells()[100]
    lat, lon = zone_center(zone)
    trip = TripRequest("R1", 0.0, lat, lon, lat, lon, zone, zone)
    engine = SimulationEngine(
        clock=SimulationClock(end_time_min=10.0, step_min=5.0),
        drivers=[],
        trips=[trip],
        max_wait_time_min=5.0,
    )
    engine.run()
    assert engine.metrics.cancelled_trips == 1
    assert engine.metrics.unserved_arrived_trips == 1
    assert any(event["type"] == "request_cancelled" for event in engine.events)


def test_p7_behavior_changes_seeded_rider_outcomes() -> None:
    zone = toronto_zone_cells()[100]
    lat, lon = zone_center(zone)
    trips = [
        TripRequest(f"R{i}", 0.0, lat, lon, lat, lon, zone, zone)
        for i in range(2)
    ]
    engine = SimulationEngine(
        clock=SimulationClock(end_time_min=0.0),
        drivers=[],
        trips=trips,
        policy_settings=POLICY_REGISTRY[PolicyId.P7],
        behavior=BehaviorConfig(rider_price_elasticity=-10.0),
        random_seed=7,
    )
    engine.run()
    assert engine.metrics.rider_price_declines == 2
    assert engine.metrics.unserved_arrived_trips == 2


def test_driver_bonus_response_materially_changes_seeded_outcome() -> None:
    zone = toronto_zone_cells()[100]
    lat, lon = zone_center(zone)
    trip = TripRequest("R1", 0.0, lat, lon, lat, lon, zone, zone)
    settings = PolicySettings(
        PolicyId.P2,
        use_driver_bonuses=True,
        use_behavior=True,
    )

    def run(driver_elasticity: float) -> SimulationEngine:
        engine = SimulationEngine(
            clock=SimulationClock(end_time_min=0.0),
            drivers=[Driver("D1", lat, lon, "oversupplied")],
            trips=[trip],
            policy_settings=settings,
            behavior=BehaviorConfig(driver_bonus_elasticity=driver_elasticity),
            acceptance=OfferAcceptanceConfig(
                intercept=0.0,
                earnings_per_cad=0.0,
                pickup_minutes_penalty=0.0,
            ),
            random_seed=5,
        )
        engine.run()
        return engine

    assert run(0.0).metrics.assigned_trips == 0
    assert run(12.0).metrics.assigned_trips == 1


def test_actual_subsidy_spend_never_exceeds_total_budget() -> None:
    zone = toronto_zone_cells()[100]
    lat, lon = zone_center(zone)
    trips = [
        TripRequest(f"R{i}", 0.0, lat, lon, lat, lon, zone, zone)
        for i in range(2)
    ]
    drivers = [
        Driver(f"D{i}", lat, lon, "oversupplied")
        for i in range(2)
    ]
    engine = SimulationEngine(
        clock=SimulationClock(end_time_min=10.0, step_min=1.0),
        drivers=drivers,
        trips=trips,
        policy_settings=POLICY_REGISTRY[PolicyId.P2],
        policy_cfg={"subsidy_budget_cad": 1.0},
        acceptance=OfferAcceptanceConfig(
            intercept=40.0,
            earnings_per_cad=0.0,
            pickup_minutes_penalty=0.0,
        ),
    )
    engine.run()
    assert engine.metrics.subsidy_spend_cad <= 1.0


def test_seeded_repositioning_consumes_time_before_location_change() -> None:
    origin_zone, supply_zone = toronto_zone_cells()[100:102]
    origin = zone_center(origin_zone)
    supply = zone_center(supply_zone)
    trip = TripRequest(
        "R1",
        0.0,
        *origin,
        *origin,
        origin_zone,
        origin_zone,
    )
    engine = SimulationEngine(
        clock=SimulationClock(end_time_min=30.0, step_min=1.0),
        drivers=[
            Driver("D0", *supply, supply_zone),
            Driver("D1", *supply, supply_zone),
        ],
        trips=[trip],
        policy_settings=POLICY_REGISTRY[PolicyId.P7],
        behavior=BehaviorConfig(
            rider_price_elasticity=0.0,
            reposition_acceptance=1.0,
        ),
        random_seed=9,
    )

    first = engine.step()

    assert first["reposition_events"] == 2
    assert engine.metrics.total_reposition_time_min > 0.0
    assert all(driver.status == DriverStatus.REPOSITIONING for driver in engine.drivers)
    assert all((driver.lat, driver.lon) == supply for driver in engine.drivers)
