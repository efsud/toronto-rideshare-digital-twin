"""Firm rider quotes followed by driver choice among competing requests."""

from dataclasses import asdict

import networkx as nx

from toronto_rideshare.marketplace.decisions import (
    choose_request,
    driver_choice_probabilities,
    quote_trip,
    rider_quote_probability,
)
from toronto_rideshare.marketplace.matching import estimate_route, min_to_departure_time
from toronto_rideshare.simulation.engine import zone_demand_supply
from toronto_rideshare.supply.models import DriverStatus


def committed_subsidy(engine):
    return sum(q.subsidy_cad for q in engine.quotes.values()) + sum(
        m.get("subsidy_cad", 0) for m in engine._active_movements.values()
    )


def step_daily(engine):
    now = min(engine.clock.current_time_min, engine.clock.end_time_min)
    engine._processed_time = now
    events = []
    engine._advance_movements(now, events)
    while (
        engine._trip_index < len(engine.trips)
        and engine.trips[engine._trip_index].request_time_min <= now
    ):
        trip = engine.trips[engine._trip_index]
        engine.pending.append(trip)
        engine._trip_index += 1
        events.append(
            {
                "type": "request_arrived",
                "request_id": trip.request_id,
                "origin": [trip.origin_lat, trip.origin_lon],
                "destination": [trip.destination_lat, trip.destination_lon],
            }
        )
    for trip in list(engine.pending):
        if now - trip.request_time_min >= engine.max_wait_time_min:
            engine.pending.remove(trip)
            engine.quotes.pop(trip.request_id, None)
            engine.quote_routes.pop(trip.request_id, None)
            engine.metrics.cancelled_trips += 1
            engine.metrics.unserved_trips += 1
            events.append(
                {
                    "type": "request_cancelled",
                    "request_id": trip.request_id,
                    "reason": "maximum unassigned queue wait",
                    "wait_min": now - trip.request_time_min,
                }
            )

    # All new quotes at an epoch see the same pre-response market state.
    imbalance = zone_demand_supply(engine.pending, engine.drivers)

    def shortage(zone):
        return imbalance.get(zone, {}).get("imbalance", 0.0)

    settings, cfg = engine.policy_settings, engine.policy_cfg
    for trip in list(engine.pending):
        if trip.request_id in engine.quotes:
            continue
        try:
            route = estimate_route(
                (trip.origin_lat, trip.origin_lon),
                (trip.destination_lat, trip.destination_lon),
                routing=engine.routing,
                departure_time=min_to_departure_time(now),
            )
        except nx.NetworkXNoPath:
            events.append(
                {
                    "type": "quote_unavailable",
                    "request_id": trip.request_id,
                    "reason": "No directed occupied route; waiting until queue expiry",
                }
            )
            continue
        budget = max(
            0,
            cfg.get("subsidy_budget_cad", 500)
            - engine.metrics.subsidy_spend_cad
            - committed_subsidy(engine),
        )
        quote = quote_trip(
            trip.request_id,
            now,
            route.distance_km,
            route.travel_time_min,
            shortage(trip.origin_zone),
            shortage(trip.destination_zone),
            adaptive=bool(settings and settings.use_od_pricing),
            rider_cap=cfg.get("max_rider_premium_cad", 5),
            bonus_cap=cfg.get("max_driver_bonus_cad", 12),
            origin_gain=cfg.get("od_origin_gain", 0.5),
            transfer_gain=cfg.get("od_transfer_gain", 1),
            discount_gain=cfg.get("od_discount_gain", 0.5),
            available_budget=budget,
        )
        events.append(
            {
                "type": "price_proposed",
                "request_id": trip.request_id,
                "quote": asdict(quote),
                "routing_source": route.mode,
                "origin_zone": trip.origin_zone,
                "destination_zone": trip.destination_zone,
            }
        )
        probability = rider_quote_probability(
            quote,
            intercept=engine.daily_behavior.get("rider_intercept", 2),
            price_per_cad=engine.daily_behavior.get("rider_price_per_cad", 0.08),
        )
        draw = engine._draw("rider_quote", trip.request_id)
        accepted = draw < probability
        events.append(
            {
                "type": "rider_quote_accepted" if accepted else "rider_price_declined",
                "request_id": trip.request_id,
                "rider_payment_cad": quote.fare.rider_payment_cad,
                "probability": probability,
                "draw": draw,
            }
        )
        if accepted:
            engine.quotes[trip.request_id] = quote
            engine.quote_routes[trip.request_id] = route
        else:
            engine.pending.remove(trip)
            engine.metrics.rider_price_declines += 1
            engine.metrics.unserved_trips += 1

    # Map prices summarize quotes offered this step at each origin; OD quotes remain inspectable.
    offered = {}
    for event in events:
        if event["type"] == "price_proposed":
            offered.setdefault(event["origin_zone"], []).append(event["quote"]["fare"])
    engine._last_adjustments = {
        zone: (
            sum(f["rider_adjustment_cad"] for f in fares) / len(fares),
            sum(f["driver_bonus_cad"] for f in fares) / len(fares),
        )
        for zone, fares in offered.items()
    }

    # Seeded rotating driver priority resolves competition without double booking.
    # Every driver chooses once from the still-available menu, or stays idle.
    available = [
        d for d in engine.drivers if d.status == DriverStatus.IDLE and d.available_time_min <= now
    ]
    available.sort(key=lambda d: (engine._draw("driver_priority", now, d.driver_id), d.driver_id))
    engine._last_assignment_backend = "sequential multinomial driver choice with outside option"
    for driver in available:
        menu, routes, requests = [], {}, {}
        for trip in engine.pending:
            if trip.request_id not in engine.quotes:
                continue
            try:
                pickup = estimate_route(
                    (driver.lat, driver.lon),
                    (trip.origin_lat, trip.origin_lon),
                    routing=engine.routing,
                    departure_time=min_to_departure_time(now),
                )
                occupied = estimate_route(
                    (trip.origin_lat, trip.origin_lon),
                    (trip.destination_lat, trip.destination_lon),
                    routing=engine.routing,
                    departure_time=min_to_departure_time(now + pickup.travel_time_min),
                )
            except nx.NetworkXNoPath:
                continue
            quote = engine.quotes[trip.request_id]
            menu.append(
                (
                    trip.request_id,
                    quote.fare.driver_earnings_cad,
                    pickup.travel_time_min,
                    occupied.travel_time_min,
                )
            )
            routes[trip.request_id] = (pickup, occupied)
            requests[trip.request_id] = trip
        if not menu:
            continue
        probs = driver_choice_probabilities(
            menu,
            intercept=engine.acceptance.intercept,
            earnings_per_cad=engine.acceptance.earnings_per_cad,
            pickup_penalty=engine.acceptance.pickup_minutes_penalty,
            occupied_penalty=engine.daily_behavior.get("driver_occupied_penalty", 0.02),
        )
        draw = engine._draw("driver_choice", now, driver.driver_id)
        chosen = choose_request(probs, draw)
        events.append(
            {
                "type": "driver_choice",
                "driver_id": driver.driver_id,
                "request_id": chosen,
                "draw": draw,
                "outside_probability": probs[None],
                "menu": [
                    {
                        "request_id": ident,
                        "gross_earnings_cad": pay,
                        "pickup_min": pickup,
                        "occupied_min": occupied,
                        "probability": probs[ident],
                    }
                    for ident, pay, pickup, occupied in menu
                ],
            }
        )
        engine.metrics.total_offers += 1
        if chosen is None:
            engine.metrics.rejected_offers += 1
            continue
        trip = requests[chosen]
        pickup, occupied = routes[chosen]
        quote = engine.quotes.pop(chosen)
        engine.quote_routes.pop(chosen, None)
        fare = quote.fare  # Never reprice after the rider accepts.
        engine.pending.remove(trip)
        engine._record_route(pickup)
        engine._record_route(occupied)
        driver.status = DriverStatus.EN_ROUTE_PICKUP
        driver.available_time_min = now + pickup.travel_time_min
        engine._active_movements[driver.driver_id] = {
            "driver_id": driver.driver_id,
            "request_id": chosen,
            "phase": "en_route_pickup",
            "request_time_min": trip.request_time_min,
            "path": list(pickup.path),
            "trip_path": list(occupied.path),
            "edge_keys": list(pickup.edge_keys),
            "trip_edge_keys": list(occupied.edge_keys),
            "routing_source": pickup.mode,
            "trip_routing_source": occupied.mode,
            "start_time_min": now,
            "pickup_time_min": driver.available_time_min,
            "end_time_min": driver.available_time_min + occupied.travel_time_min,
            "start": [driver.lat, driver.lon],
            "origin": [trip.origin_lat, trip.origin_lon],
            "destination": [trip.destination_lat, trip.destination_lon],
            "origin_zone": trip.origin_zone,
            "destination_zone": trip.destination_zone,
            "rider_payment_cad": fare.rider_payment_cad,
            "driver_earnings_cad": fare.driver_earnings_cad,
            "subsidy_cad": quote.subsidy_cad,
        }
        engine.metrics.accepted_offers += 1
        engine.metrics.assigned_trips += 1
        engine.metrics.total_queue_wait_min += now - trip.request_time_min
        engine.metrics.total_pickup_time_min += pickup.travel_time_min
        engine.metrics.total_trip_time_min += occupied.travel_time_min
        events.append(
            {
                "type": "offer_accepted",
                "request_id": chosen,
                "driver_id": driver.driver_id,
                "origin": [trip.origin_lat, trip.origin_lon],
                "destination": [trip.destination_lat, trip.destination_lon],
                "rider_payment_cad": fare.rider_payment_cad,
                "driver_earnings_cad": fare.driver_earnings_cad,
                "driver_bonus_cad": fare.driver_bonus_cad,
                "probability": probs[chosen],
                "draw": draw,
            }
        )
    if settings and settings.use_repositioning:
        engine._reposition(now, events)
    engine._advance_movements(now, events)
    engine.events.extend({"time_min": now, **event} for event in events)
    if now >= engine.clock.end_time_min:
        engine.finished = True
        engine.metrics.not_yet_released_trips = len(engine.trips) - engine._trip_index
        engine.metrics.unserved_trips += len(engine.pending)
        engine.metrics.unserved_arrived_trips = engine.metrics.unserved_trips
    else:
        engine.clock.advance()
    engine._refresh_derived_metrics()
    engine.last_snapshot = engine.snapshot(events)
    engine.last_snapshot["quotes"] = {ident: asdict(q) for ident, q in engine.quotes.items()}
    engine.last_snapshot["committed_subsidy_cad"] = committed_subsidy(engine)
    engine.history.append(
        {
            "time_min": now,
            **asdict(engine.metrics),
            "zone_state": engine.last_snapshot["zone_state"],
        }
    )
    return engine.last_snapshot
