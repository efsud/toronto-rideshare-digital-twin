"""Truthful map payloads and plain-language labels shared by UI and tests."""

from __future__ import annotations

from html import escape

from shapely.geometry import mapping

from toronto_rideshare.policies.registry import POLICY_REGISTRY, PolicyId
from toronto_rideshare.zones import toronto_zone_cells
from toronto_rideshare.zones.sampling import clipped_zone

POLICY_NAMES = dict(
    zip(
        PolicyId,
        (
            "P0 · Fixed-price baseline",
            "P1 · Rider pricing",
            "P2 · Driver incentives",
            "P3 · Two-sided rules",
            "P4 · Optimized pricing and matching",
            "P5 · Repositioning",
            "P6 · Rules plus repositioning",
            "P7 · Optimization plus repositioning",
        ),
        strict=True,
    )
)
STATE_NAMES = {
    "idle": "Driver available",
    "en_route_pickup": "Driver heading to pickup",
    "with_rider": "Driver carrying rider",
    "repositioning": "Driver repositioning",
}
ZONE_METRICS = {
    "Waiting demand": ("demand", "requests"),
    "Idle supply": ("supply", "drivers"),
    "Shortage": ("imbalance", "requests minus idle drivers"),
    "Rider adjustment": ("rider_premium_cad", "CAD per trip"),
    "Driver bonus": ("driver_bonus_cad", "CAD per trip"),
}
LEGEND = (
    "Toronto study boundary",
    "Analysis zones — H3 resolution 8",
    "Waiting pickup",
    "Requested destination",
    *STATE_NAMES.values(),
    "Accepted offer — latest step",
    "Rejected offer — latest step",
    "Road-network route",
    "Straight-line estimate — illustrative",
)


def policy_rows():
    return [
        {
            "Policy": POLICY_NAMES[p],
            "Rider adjustment": "LP proxy"
            if s.use_ortools
            else "Imbalance rule"
            if s.use_rider_pricing
            else "None",
            "Driver bonus": "LP proxy"
            if s.use_ortools
            else "Imbalance rule"
            if s.use_driver_bonuses
            else "None",
            "Matching": s.matching_strategy,
            "Repositioning": s.use_repositioning,
        }
        for p, s in POLICY_REGISTRY.items()
    ]


def zone_features(snapshot, metric):
    key, unit = ZONE_METRICS[metric]
    values = [float(row.get(key, 0)) for row in snapshot["zone_state"].values()]
    extent = max([1.0, *(abs(v) for v in values)])
    features = []
    for zone in toronto_zone_cells():
        row = snapshot["zone_state"].get(zone, {})
        value = float(row.get(key, 0))
        strength = min(1.0, abs(value) / extent)
        end = (183, 79, 20) if value > 0 else (34, 110, 156)
        color = [int(238 + (v - 238) * strength) for v in end] + [150]
        features.append(
            {
                "type": "Feature",
                "geometry": mapping(clipped_zone(zone)),
                "tooltip": f"Zone {zone}<br>{metric}: {value:g} {unit}",
                "properties": {
                    "entity_id": zone,
                    "value": value,
                    "color": color,
                    "tooltip": f"Zone {zone}<br>{metric}: {value:g} {unit}",
                },
            }
        )
    return features, extent


def map_entities(snapshot):
    rows = []
    colors = {
        "idle": [26, 105, 83],
        "en_route_pickup": [165, 92, 18],
        "with_rider": [34, 93, 158],
        "repositioning": [115, 73, 149],
    }
    for driver in snapshot["drivers"]:
        movement = driver.get("movement") or {}
        label = STATE_NAMES[driver["status"]]
        ident = driver["driver_id"]
        text = f"{ident} · {label}"
        arrival = (
            movement.get("pickup_time_min")
            if driver["status"] == "en_route_pickup"
            else movement.get("end_time_min", "—")
        )
        tooltip = (
            f"<b>{text}</b><br>Request: {movement.get('request_id', '—')}"
            f"<br>Leg: {movement.get('phase', 'none')}"
            f"<br>Arrival minute: {arrival}"
            f"<br>Routing: {movement.get('routing_source', 'not moving')}"
        )
        rows.append(
            {
                "entity_id": ident,
                "label": label,
                "symbol": "▣",
                "lat": driver["lat"],
                "lon": driver["lon"],
                "color": colors[driver["status"]],
                "tooltip": tooltip,
            }
        )
    for trip in snapshot["pending_requests"]:
        for prefix, symbol, label, color in (
            ("origin", "●", "Waiting pickup", [165, 92, 18]),
            ("destination", "◆", "Requested destination", [115, 73, 149]),
        ):
            rows.append(
                {
                    "entity_id": trip["request_id"] + ":" + prefix,
                    "label": label,
                    "symbol": symbol,
                    "lat": trip[prefix + "_lat"],
                    "lon": trip[prefix + "_lon"],
                    "color": color,
                    "tooltip": escape(trip["request_id"] + " · " + label),
                }
            )
    for index, event in enumerate(snapshot["offers"]):
        accepted = event["type"] == "offer_accepted"
        label = "Accepted offer — latest step" if accepted else "Rejected offer — latest step"
        rows.append(
            {
                "entity_id": f"offer:{index}",
                "label": label,
                "symbol": "✓" if accepted else "×",
                "lat": event["origin"][0],
                "lon": event["origin"][1],
                "color": [26, 105, 83] if accepted else [160, 45, 55],
                "tooltip": f"{label}<br>{event['request_id']} / {event['driver_id']}"
                f"<br>Acceptance probability: {event['probability']:.2f}",
            }
        )
    return rows


def movement_paths(snapshot):
    rows = []
    for movement in snapshot["active_movements"]:
        path = movement.get("path", [])
        if len(path) < 2:
            continue
        illustrative = movement.get("routing_source") == "haversine fallback"
        paths = [path]
        if illustrative:
            a, b = path[0], path[-1]
            paths = [
                [
                    [a[0] + (b[0] - a[0]) * t / 20, a[1] + (b[1] - a[1]) * t / 20],
                    [
                        a[0] + (b[0] - a[0]) * (t + 0.55) / 20,
                        a[1] + (b[1] - a[1]) * (t + 0.55) / 20,
                    ],
                ]
                for t in range(20)
            ]
        label = "Straight-line estimate — illustrative" if illustrative else "Road-network route"
        rows.extend(
            {
                "entity_id": movement["driver_id"],
                "path": p,
                "tooltip": f"{label}<br>{movement['driver_id']} · {movement['phase']}",
            }
            for p in paths
        )
    return rows
