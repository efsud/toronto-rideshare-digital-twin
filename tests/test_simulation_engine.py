from toronto_rideshare.demand import generate_trips
from toronto_rideshare.simulation import SimulationClock, SimulationEngine
from toronto_rideshare.supply import initialize_fleet
from toronto_rideshare.zones import lat_lon_to_zone


def test_simulation_engine_completes_trips() -> None:
    zone = lat_lon_to_zone(43.65, -79.38)
    trips = generate_trips([zone], n_trips=3, random_seed=0)
    drivers = initialize_fleet([zone], fleet_size=3, random_seed=0)
    clock = SimulationClock(end_time_min=200.0, step_min=5.0)
    engine = SimulationEngine(clock=clock, drivers=drivers, trips=trips)
    metrics = engine.run()
    assert metrics.completed_trips >= 1
