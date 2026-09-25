import networkx as nx

from toronto_rideshare.demand.models import TripRequest
from toronto_rideshare.marketplace.matching import RoutingContext, greedy_match
from toronto_rideshare.supply.models import Driver


def _tiny_graph() -> nx.MultiDiGraph:
    graph = nx.MultiDiGraph()
    graph.add_node(1, y=43.65, x=-79.38)
    graph.add_node(2, y=43.651, x=-79.379)
    graph.add_edge(1, 2, 0, length=500.0, travel_time=60.0, highway="residential")
    graph.add_edge(2, 1, 0, length=500.0, travel_time=60.0, highway="residential")
    graph.graph["crs"] = "EPSG:4326"
    return graph


def test_greedy_match_with_routing_context() -> None:
    trip = TripRequest(
        request_id="R1",
        request_time_min=0.0,
        origin_lat=43.65,
        origin_lon=-79.38,
        destination_lat=43.651,
        destination_lon=-79.379,
        origin_zone="z1",
        destination_zone="z2",
    )
    driver = Driver(driver_id="D1", lat=43.65, lon=-79.38, zone="z1")
    routing = RoutingContext(graph=_tiny_graph(), profile=None, use_time_dependent=False)
    matches = greedy_match([trip], [driver], current_time_min=0.0, routing=routing)
    assert len(matches) == 1
    _, _, pickup_min, trip_min, _fare = matches[0]
    assert pickup_min >= 0.0
    assert trip_min >= 0.0
