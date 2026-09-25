"""Guided research workspace. Synthetic evidence is always labeled."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pydeck as pdk
import streamlit as st

from toronto_rideshare.experiments.runner import create_engine, run_repeated_policy_comparison
from toronto_rideshare.manifest import METRIC_DEFINITIONS, run_manifest
from toronto_rideshare.policies.registry import ACTIVE_POLICIES, PolicyId
from toronto_rideshare.presentation import (
    LEGEND,
    POLICY_NAMES,
    ZONE_METRICS,
    map_entities,
    movement_paths,
    policy_rows,
    zone_features,
)
from toronto_rideshare.scenario import ScenarioConfig
from toronto_rideshare.zones import toronto_boundary_geojson

ROOT = Path(__file__).resolve().parents[1]


def metric_label(name):
    return {
        "mean_wait_min": "Realized pickup wait (minutes)",
        "platform_net_revenue_cad": "Platform contribution before costs (CAD)",
        "driver_earnings_cad": "Driver gross earnings (CAD)",
        "rider_payment_cad": "Rider payments (CAD)",
        "subsidy_spend_cad": "Settled subsidies (CAD)",
    }.get(name, name.replace("_", " ").capitalize())


def clock_label(minutes):
    return f"{int(minutes) // 60:02d}:{int(minutes) % 60:02d}"


def setup_view():
    st.subheader("Set up a scenario")
    st.caption("Change one assumption at a time. Applying changes creates a fresh run.")
    if st.button("Load full-day adaptive-demand scenario"):
        scenario = ScenarioConfig.from_source(ROOT / "configs/experiments/full_day.yaml").as_dict()
        st.session_state.scenario = scenario
        st.session_state.engine = create_engine(scenario)
        st.session_state.pop("comparison", None)
        st.rerun()
    config = ScenarioConfig.from_source(st.session_state.scenario).as_dict()
    sim, policy, network = config["simulation"], config["policy"], config["network"]
    a, b = st.columns(2)
    with a:
        policy["name"] = st.selectbox(
            "Policy",
            list(ACTIVE_POLICIES),
            index=list(ACTIVE_POLICIES).index(PolicyId(policy["name"])),
            format_func=lambda p: POLICY_NAMES[p],
            key="scenario_policy",
        )
        sim["fleet_size"] = st.number_input("Drivers in the fleet", 0, 200, sim["fleet_size"])
        sim["base_trip_count"] = st.number_input(
            "Potential requests", 0, 2000, sim["base_trip_count"]
        )
        sim["demand_profile"] = st.selectbox(
            "Demand geography through time",
            ["uniform", "synthetic_daily"],
            index=["uniform", "synthetic_daily"].index(sim["demand_profile"]),
            help="Synthetic daily regimes reverse central/peripheral trip flows over the day.",
        )
        sim["request_probability"] = st.number_input(
            "Probability a potential rider requests a ride",
            0.0,
            1.0,
            float(sim["request_probability"]),
            0.05,
            help="Shared across policies; separate from acceptance of the quoted price.",
        )
        sim["demand_multiplier"] = st.number_input(
            "Demand multiplier", 0.0, 4.0, float(sim["demand_multiplier"]), 0.1
        )
    with b:
        sim["start_time"] = st.text_input("Start time · Toronto local time", sim["start_time"])
        sim["end_time"] = st.text_input("End time · 24:00 for a full day", sim["end_time"])
        sim["decision_interval_minutes"] = st.number_input(
            "Decision interval (minutes)", 0.25, 60.0, float(sim["decision_interval_minutes"])
        )
        config["project"]["random_seed"] = st.number_input(
            "Reproducible seed", 0, value=int(config["project"]["random_seed"])
        )
    network["mode"] = st.radio(
        "Travel model",
        ["demo", "network_research"],
        horizontal=True,
        index=["demo", "network_research"].index(network["mode"]),
        format_func=lambda x: "Illustrative demo" if x == "demo" else "Network research",
    )
    st.caption(
        "Demo uses straight-line estimates. Network research requires a "
        "local graph and excludes unreachable assignments."
    )
    with st.expander("Shared behavior and pricing assumptions"):
        st.caption(
            "Every policy uses these same rider and driver response functions. "
            "Drivers choose among requests or stay idle; P5 also repositions idle drivers."
        )
        behavior = config["behavior"]
        for key, label, low, high in (
            ("rider_intercept", "Rider acceptance intercept", -10.0, 10.0),
            ("rider_price_per_cad", "Rider total-price sensitivity (per CAD)", 0.0, 2.0),
            ("driver_occupied_penalty", "Driver occupied-time penalty (per minute)", 0.0, 1.0),
        ):
            behavior[key] = st.number_input(label, low, high, float(behavior[key]))
        for key, label, low, high in (
            ("acceptance_intercept", "Driver choice intercept", -10.0, 10.0),
            ("acceptance_earnings_per_cad", "Driver gross-pay sensitivity (per CAD)", 0.0, 1.0),
            ("acceptance_pickup_minutes_penalty", "Driver pickup penalty (per minute)", 0.0, 1.0),
            ("reposition_acceptance", "Reposition acceptance probability", 0.0, 1.0),
            ("max_rider_premium_cad", "Rider adjustment cap (CAD)", 0.0, 50.0),
            ("max_driver_bonus_cad", "Driver bonus cap (CAD)", 0.0, 50.0),
            ("subsidy_budget_cad", "Total subsidy budget (CAD)", 0.0, 10000.0),
            ("od_origin_gain", "Origin shortage price gain", 0.0, 5.0),
            ("od_transfer_gain", "Destination transfer bonus gain", 0.0, 5.0),
            ("od_discount_gain", "Destination transfer discount gain", 0.0, 5.0),
        ):
            policy[key] = st.number_input(label, low, high, float(policy[key]))
        sim["rider_max_wait_minutes"] = st.number_input(
            "Maximum unassigned queue wait (minutes)",
            0.25,
            120.0,
            float(sim["rider_max_wait_minutes"]),
        )
        st.caption(
            "Base fare: CAD 3.50 + 1.10/km + 0.35/occupied minute; driver share 75%. "
            "Assumed prices. Adaptive gains affect only origin–destination pricing."
        )
    with st.expander("Advanced data paths"):
        network["graph_path"] = st.text_input("Road graph (GraphML)", network["graph_path"])
        network["traffic_profile_path"] = st.text_input(
            "Traffic profile (Parquet)", network["traffic_profile_path"]
        )
        network["use_time_dependent_routing"] = st.checkbox(
            "Use departure-bucket traffic costs", network["use_time_dependent_routing"]
        )
    changed = config != st.session_state.scenario
    if changed:
        st.info("Pending changes — the active run still uses the previous scenario.")
    if st.button("Apply scenario and start fresh", type="primary"):
        try:
            scenario = ScenarioConfig.from_source(config).as_dict()
            engine = create_engine(scenario)
        except (ValueError, OSError, KeyError) as exc:
            st.error(str(exc))
        else:
            st.session_state.scenario = scenario
            st.session_state.engine = engine
            st.session_state.pop("comparison", None)
            st.success("Scenario applied. Open Explore the simulation to begin.")
    st.download_button(
        "Download active scenario",
        json.dumps(st.session_state.scenario, indent=2),
        "scenario.json",
        "application/json",
    )


def render_map(engine):
    snapshot = engine.last_snapshot
    metric = st.selectbox("Color zones by", list(ZONE_METRICS), index=2)
    enabled = st.multiselect(
        "Visible layers",
        ["Analysis zones", "Drivers", "Requests", "Latest offers", "Movement paths"],
        default=["Analysis zones", "Drivers", "Requests", "Movement paths"],
    )
    features, extent = zone_features(snapshot, metric)
    layers = [
        pdk.Layer(
            "GeoJsonLayer",
            toronto_boundary_geojson(),
            id="boundary",
            filled=False,
            stroked=True,
            get_line_color=[23, 43, 58],
            get_line_width=2,
            line_width_min_pixels=2,
        )
    ]
    if "Analysis zones" in enabled:
        layers.insert(
            0,
            pdk.Layer(
                "GeoJsonLayer",
                {"type": "FeatureCollection", "features": features},
                id="zones",
                filled=True,
                get_fill_color="properties.color",
                get_line_color=[150, 165, 170, 80],
                line_width_min_pixels=0.4,
                pickable=True,
                auto_highlight=True,
            ),
        )
    entities = map_entities(snapshot)
    visible = [
        r
        for r in entities
        if ("Drivers" in enabled and r["entity_id"].startswith("D"))
        or ("Requests" in enabled and r["entity_id"].startswith("R"))
        or ("Latest offers" in enabled and r["entity_id"].startswith("offer:"))
    ]
    if visible:
        layers.append(
            pdk.Layer(
                "TextLayer",
                visible,
                id="entities",
                get_position="[lon, lat]",
                get_text="symbol",
                character_set=pdk.types.String("auto"),
                get_color="color",
                get_size=22,
                pickable=True,
            )
        )
    if "Movement paths" in enabled:
        layers.append(
            pdk.Layer(
                "PathLayer",
                movement_paths(snapshot),
                id="paths",
                get_path="path",
                get_color=[34, 93, 158],
                width_min_pixels=2,
                pickable=True,
            )
        )
    deck = pdk.Deck(
        layers=layers,
        map_style="light",
        initial_view_state=pdk.ViewState(latitude=43.70, longitude=-79.39, zoom=9.4),
        tooltip={"html": "{tooltip}"},
    )
    event = st.pydeck_chart(
        deck, height=560, key="market_map", on_select="rerun", selection_mode="single-object"
    )
    if metric in ("Rider adjustment", "Driver bonus"):
        st.caption(
            "Mean quote adjustment at each origin in the latest epoch; "
            "inspect trips for OD-specific prices."
        )
    st.caption(
        f"{metric} · {ZONE_METRICS[metric][1]} · scale −{extent:g} to +{extent:g}. "
        "Blue: negative; neutral: zero; amber: positive."
    )
    with st.expander("Map legend — what every mark means", expanded=True):
        st.markdown(
            "**Dark outline:** Toronto study boundary · **Hexagons:** H3 "
            "analysis zones, clipped for display.\n\n"
            "**●** Waiting pickup · **◆** Requested destination · **▣** "
            "Driver (state in tooltip)\n\n"
            "**✓ / ×** Accepted trip / driver chose to stay idle, latest step only\n\n"
            "**Solid link:** Road-network route · **Segmented link:** "
            "Straight-line estimate — illustrative"
        )
        st.caption(
            "Driver colors: green = available; amber = heading to pickup; "
            "blue = carrying rider; purple = repositioning. Positions update "
            "at endpoints, not as live GPS."
        )
    selected = None
    if event and hasattr(event, "selection"):
        for objects in event.selection.get("objects", {}).values():
            if objects:
                selected = objects[0].get("entity_id") or objects[0].get("properties", {}).get(
                    "entity_id"
                )
    zones = [
        {
            "entity_id": f["properties"]["entity_id"],
            "label": "Analysis zone",
            "value": f["properties"]["value"],
        }
        for f in features
    ]
    lookup = {row["entity_id"]: row for row in [*entities, *zones]}
    if selected in lookup:
        st.session_state["selected_entity"] = selected
    if st.session_state.get("selected_entity") not in lookup:
        st.session_state["selected_entity"] = next(iter(lookup))
    choice = st.selectbox(
        "Inspect an agent or zone (keyboard alternative)", list(lookup), key="selected_entity"
    )
    st.json(
        {k: v for k, v in lookup[choice].items() if k not in ("tooltip", "color")}, expanded=False
    )
    query = st.text_input("Search the map data by ID or state")
    table = pd.DataFrame(
        [
            {k: v for k, v in row.items() if k not in ("tooltip", "color")}
            for row in [*entities, *zones]
        ]
    )
    if query:
        table = table[
            table.astype(str).apply(
                lambda row: row.str.contains(query, case=False, regex=False).any(), axis=1
            )
        ]
    with st.expander("Accessible map data table"):
        st.dataframe(table, hide_index=True, width="stretch")


def advance_minutes(engine, minutes):
    target = min(engine.clock.end_time_min, engine.last_snapshot["processed_time_min"] + minutes)
    while not engine.finished and engine.clock.current_time_min <= target:
        engine.step()


def explore_view():
    engine = st.session_state.engine
    st.subheader("Explore the simulation")
    sim = st.session_state.scenario["simulation"]
    step = sim["decision_interval_minutes"]
    cols = st.columns([1, 1.3, 1.4])
    if cols[0].button("Reset scenario", key="reset"):
        engine.reset()
    if cols[1].button(
        f"Advance {step:g} minutes", key="step", type="primary", disabled=engine.finished
    ):
        advance_minutes(engine, step)
    if cols[2].button(f"Run next {step * 6:g} minutes", key="run_steps", disabled=engine.finished):
        advance_minutes(engine, step * 6)
    if st.button("Run to end of day / scenario", disabled=engine.finished):
        with st.spinner("Simulating all remaining decisions…"):
            while not engine.finished:
                engine.step()
    snapshot = engine.last_snapshot
    st.caption(
        f"Processed through {clock_label(snapshot['processed_time_min'])} · "
        + (
            "Horizon reached"
            if engine.finished
            else f"Next decision {clock_label(snapshot['next_decision_time_min'])}"
        )
    )
    if engine.routing is None:
        st.warning(
            "Illustrative demo · haversine fallback. Distances and times are "
            "straight-line estimates, not Toronto road measurements."
        )
    else:
        st.info(
            f"Network research · {snapshot['routing_mode']} · unreachable assignments excluded."
        )
    m = snapshot["metrics"]
    cols = st.columns(4)
    for col, label, value, help_text in zip(
        cols,
        ["Completed trips", "Waiting / in progress", "Realized pickup wait", "Vehicle utilization"],
        [
            m["completed_trips"],
            f"{m['waiting_trips']} / {m['in_progress_trips']}",
            f"{m['mean_wait_min']:.1f} min" if m["picked_up_trips"] else "No pickups yet",
            f"{m['utilization_rate']:.1%}",
        ],
        [
            "Drop-offs by the processed time",
            "Arrived unassigned / accepted unfinished",
            METRIC_DEFINITIONS["mean_wait_min"],
            METRIC_DEFINITIONS["utilization_rate"],
        ],
        strict=True,
    ):
        col.metric(label, value, help=help_text, border=True)
    render_map(engine)
    if engine.history:
        st.subheader("How the day changes")
        history = pd.DataFrame(
            [
                {k: v for k, v in row.items() if k not in ("zone_state", "routing_mode_counts")}
                for row in engine.history
            ]
        )
        st.line_chart(
            history, x="time_min", y=["completed_trips", "waiting_trips", "in_progress_trips"]
        )
        st.caption(
            "Elapsed minutes from midnight. Counts are cumulative for completions; "
            "waiting and in-progress counts show the current population."
        )
    if engine.history and "regional_state" in engine.history[0]:
        with st.expander("Where supply and demand shift through the day", expanded=True):
            quantity = st.selectbox(
                "Regional quantity",
                ["demand", "supply", "imbalance"],
                format_func=lambda v: {
                    "demand": "Waiting riders",
                    "supply": "Available drivers",
                    "imbalance": "Waiting riders minus available drivers",
                }[v],
            )
            regional = pd.DataFrame(
                [
                    {
                        "Minute": row["time_min"],
                        **{
                            region: counts[quantity]
                            for region, counts in row["regional_state"].items()
                        },
                    }
                    for row in engine.history
                ]
            )
            st.line_chart(regional, x="Minute", y=["central", "west", "east", "north"])
            st.caption(
                "Analytical scenario regions, not official neighborhoods. "
                "Morning demand flows inward; "
                "evening demand flows outward. Lines show realized waiting demand/available supply."
            )
    with st.expander("Price proposals and rider/driver decisions", expanded=False):
        decisions = [
            e
            for e in engine.events
            if e["type"]
            in ("price_proposed", "rider_quote_accepted", "rider_price_declined", "driver_choice")
        ]
        st.caption(
            "Every driver menu includes gross pay, pickup burden and choice probability. "
            "An empty selected request means the driver stayed idle."
        )
        responses = {
            e["request_id"]: e
            for e in decisions
            if e["type"] in ("rider_quote_accepted", "rider_price_declined")
        }
        proposals = [e for e in decisions if e["type"] == "price_proposed"][-12:]
        if proposals:
            st.write("Latest rider quotes")
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "Request": e["request_id"],
                            "Offered at": clock_label(e["time_min"]),
                            "Rider price (CAD)": round(e["quote"]["fare"]["rider_payment_cad"], 2),
                            "Driver gross pay (CAD)": round(
                                e["quote"]["fare"]["driver_earnings_cad"], 2
                            ),
                            "Driver bonus (CAD)": round(e["quote"]["fare"]["driver_bonus_cad"], 2),
                            "Origin shortage": e["quote"]["origin_shortage"],
                            "Destination shortage": e["quote"]["destination_shortage"],
                            "Rider response": "Accepted"
                            if responses.get(e["request_id"], {}).get("type")
                            == "rider_quote_accepted"
                            else "Declined",
                        }
                        for e in proposals
                    ]
                ),
                hide_index=True,
                width="stretch",
            )
        menus = [e for e in decisions if e["type"] == "driver_choice"][-30:]
        if menus:
            selected = st.selectbox(
                "Driver menu to inspect",
                range(len(menus)),
                index=len(menus) - 1,
                format_func=lambda i: (
                    f"{menus[i]['driver_id']} at {clock_label(menus[i]['time_min'])}"
                ),
            )
            decision = menus[selected]
            st.write("Driver selected: " + (decision["request_id"] or "Stay idle"))
            st.caption(f"Probability of staying idle: {decision['outside_probability']:.1%}")
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "Request": item["request_id"],
                            "Gross pay (CAD)": round(item["gross_earnings_cad"], 2),
                            "Pickup (min)": round(item["pickup_min"], 1),
                            "Occupied trip (min)": round(item["occupied_min"], 1),
                            "Choice probability": f"{item['probability']:.1%}",
                            "Selected": item["request_id"] == decision["request_id"],
                        }
                        for item in decision["menu"]
                    ]
                ),
                hide_index=True,
                width="stretch",
            )
        st.json(decisions[-30:], expanded=False)
        st.metric(
            "Subsidies reserved for waiting/unfinished trips (CAD)",
            f"{snapshot.get('committed_subsidy_cad', 0):.2f}",
        )
    st.subheader("Why did that happen?")
    events = snapshot["events"]
    if not events:
        st.info(
            "No events in this step. Advance time to release requests, or "
            "increase potential demand."
        )
    for item in events[-6:]:
        label = item["type"].replace("_", " ").capitalize()
        detail = f" · {item.get('request_id', item.get('driver_id', ''))}"
        if "probability" in item:
            detail += (
                f" · acceptance probability {item['probability']:.0%}; "
                f"seeded draw {item['draw']:.2f}"
            )
        st.write(label + detail)
    with st.expander("Financial outcomes and full event log"):
        st.write(
            {
                "Rider payments (CAD)": m["total_rider_payment_cad"],
                "Driver gross earnings (CAD)": m["total_driver_earnings_cad"],
                "Platform contribution before operating costs (CAD)": m["platform_net_revenue_cad"],
                "Settled subsidies (CAD)": m["subsidy_spend_cad"],
                "Cancelled": m["cancelled_trips"],
                "Price declined": m["rider_price_declines"],
            }
        )
        st.dataframe(pd.DataFrame(engine.events), hide_index=True)
    st.download_button(
        "Export run evidence",
        json.dumps(
            {
                "manifest": run_manifest(engine.scenario, engine),
                "snapshot": snapshot,
                "events": engine.events,
                "history": engine.history,
            },
            indent=2,
        ),
        "run-evidence.json",
        "application/json",
    )


def compare_view():
    st.subheader("Compare policies")
    st.write(
        "Same scenario and behavior. P0 is always the reference; a higher "
        "policy number is not a promise of better results."
    )
    policies = st.multiselect(
        "Policies to compare",
        list(ACTIVE_POLICIES),
        default=list(ACTIVE_POLICIES),
        format_func=lambda p: POLICY_NAMES[p],
        key="comparison_policies",
    )
    n = st.number_input(
        "Paired seeds · 3 for preview, 30 for research", 1, 100, 30, key="comparison_replicates"
    )
    st.caption(
        "All three policies share the same driver-choice mechanism and behavioral parameters."
    )
    if st.button("Run policy comparison", type="primary"):
        config = ScenarioConfig.from_source(st.session_state.scenario).as_dict()
        if config["behavior"]["profile"] != "shared":
            st.warning(
                "Legacy behavior differs by policy. These are not intervention-only comparisons."
            )
        with st.spinner(
            f"Running {len(set(policies) | {PolicyId.P0})} policies × {n} paired seeds…"
        ):
            st.session_state.comparison = run_repeated_policy_comparison(
                config, policies=tuple(policies), n_replicates=n
            )
    if "comparison" not in st.session_state:
        st.info(
            "Run a comparison to see effects and uncertainty. Your applied "
            "scenario is used, including fleet, demand and behavior."
        )
        return
    result = st.session_state.comparison
    metric = st.selectbox(
        "Outcome",
        list(result["aggregates"][0]["metrics"]),
        key="comparison_metric",
        format_func=metric_label,
    )
    rows = []
    for row in result["aggregates"]:
        interval = row["metrics"][metric]
        delta = row["paired_delta_vs_p0"][metric]
        rows.append(
            {
                "Policy": POLICY_NAMES[PolicyId(row["policy_id"])],
                "Mean": interval["mean"],
                "Difference vs P0": delta["mean"],
                "Paired 95% CI low": delta["ci95_low"],
                "Paired 95% CI high": delta["ci95_high"],
            }
        )
    st.bar_chart(pd.DataFrame(rows), x="Policy", y="Difference vs P0", color="#176B5B")
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    st.caption(
        "Student-t intervals on paired seed differences. One seed: "
        "uncertainty unavailable. Simulation uncertainty is not evidence "
        "of calibration. No automatic winner is selected."
    )
    trajectories = []
    history_metric = st.selectbox(
        "Compare across the day",
        [
            "completed_trips",
            "mean_wait_min",
            "platform_net_revenue_cad",
            "waiting_trips",
            "in_progress_trips",
            "utilization_rate",
        ],
        format_func=metric_label,
    )
    for run in result["replicates"]:
        for point in run.get("daily_trajectory", []):
            trajectories.append(
                {
                    "Minute": point["time_min"],
                    "Policy": POLICY_NAMES[PolicyId(run["policy_id"])],
                    "Value": point[history_metric],
                }
            )
    if trajectories:
        curve = pd.DataFrame(trajectories).groupby(["Minute", "Policy"]).Value.mean().unstack()
        curve = curve.rename(
            columns={
                POLICY_NAMES[PolicyId.P0]: "P0 · Baseline",
                POLICY_NAMES[PolicyId.P5]: "P5 · Reposition",
                POLICY_NAMES[PolicyId.ADAPTIVE]: "Adaptive OD",
            }
        )
        curve.index = curve.index / 60
        curve.index.name = "Hour of day"
        palette = {
            "Adaptive OD": "#7B3294",
            "P0 · Baseline": "#176B5B",
            "P5 · Reposition": "#B45713",
        }
        st.line_chart(curve, color=[palette[column] for column in curve.columns])
        st.caption(
            "Mean trajectory across paired seeds; final-effect uncertainty is in the table above. "
            "Waiting-time curves are cumulative means among riders collected by that time."
        )
    st.download_button(
        "Export comparison and manifests",
        json.dumps(result, indent=2),
        "policy-comparison.json",
        "application/json",
    )
    with st.expander("Inspect exact comparison inputs"):
        st.json(result["replicates"][0]["manifest"]["scenario"])


def model_view():
    st.subheader("Understand the model")
    st.dataframe(pd.DataFrame(policy_rows()), hide_index=True, width="stretch")
    st.info(
        "Research prototype · software tests, empirical accuracy and "
        "human usability are separate evidence categories."
    )
    handbook = ROOT / "docs" / "DAILY_MARKETPLACE.md"
    if handbook.exists():
        st.markdown(handbook.read_text())
    st.subheader("Calibration and parameter tuning")
    st.write(
        "Public spot-speed data can tune road costs. Demand, rider response, and driver-choice "
        "coefficients remain explicit assumptions until suitable observations are available."
    )
    calibration_path = ROOT / "results" / "speed_calibration.json"
    if calibration_path.exists():
        report = json.loads(calibration_path.read_text())
        st.dataframe(
            pd.DataFrame(
                [
                    {"Prediction": label, **report[key]}
                    for label, key in (
                        ("Fitted road-speed scales", "calibrated"),
                        ("Free-flow baseline", "free_flow"),
                    )
                ]
            ),
            hide_index=True,
        )
        with st.expander("Fitted parameters, data scope and provenance"):
            st.json({k: v for k, v in report.items() if k not in ("training_sites", "test_sites")})
        st.caption(
            "Applying this fit selects road-network routing and starts a new run. "
            "It does not calibrate behavior."
        )
        if st.button("Apply calibrated road profile and reset scenario"):
            from toronto_rideshare.calibration import calibrated_road_scenario

            try:
                scenario = calibrated_road_scenario(st.session_state.scenario, calibration_path)
                engine = create_engine(scenario)
            except (ValueError, OSError, KeyError) as exc:
                st.error(str(exc))
            else:
                st.session_state.scenario, st.session_state.engine = scenario, engine
                st.session_state.pop("comparison", None)
                st.success("Calibrated road profile applied. Open Explore to begin the new run.")
    else:
        st.info(
            "No local road-speed calibration report. Follow the documented calibration workflow."
        )
    st.download_button(
        "Rider acceptance data template",
        "group_id,price_cad,accepted,offered\n",
        "rider-acceptance-template.csv",
        "text/csv",
    )
    st.caption(
        "Groups must keep related studies/sites/dates together. The rider fitting command reports "
        "holdout performance; synthetic recovery tests are not empirical validation."
    )
    st.subheader("Data and validation evidence")
    st.write(
        "Roads: OpenStreetMap when loaded. Demand: synthetic. Behavior: "
        "assumed. Traffic does not respond to the simulated fleet."
    )
    st.json(toronto_boundary_geojson()["metadata"], expanded=False)
    for name in (
        "DAILY_RESULTS.md",
        "CALIBRATION.md",
        "PUBLIC_DATA_REPORT.md",
        "RELEASE_READINESS.md",
    ):
        path = ROOT / "docs" / name
        if path.exists():
            with st.expander(name.replace("_", " ").removesuffix(".md").title()):
                st.markdown(path.read_text())
    st.dataframe(
        pd.DataFrame([{"Metric": k, "Meaning": v} for k, v in METRIC_DEFINITIONS.items()]),
        hide_index=True,
    )
    st.caption(
        "Map data © OpenStreetMap contributors. Boundary derived from "
        "City of Toronto Open Data ward polygons; not a legal survey."
    )
    with st.expander("Complete map vocabulary"):
        st.write(list(LEGEND))


def main():
    st.set_page_config(page_title="Toronto · Ride-hailing research", page_icon="◈", layout="wide")
    st.markdown(
        """<style>
    .block-container {max-width:1280px;padding-top:3.5rem;}
    h1 {letter-spacing:-.035em;} h2,h3 {letter-spacing:-.02em;}
    [data-testid="stMetric"] {background:white;border-radius:12px;}
    button:focus-visible, input:focus-visible {outline:3px solid #176B5B!important;}
    </style>""",
        unsafe_allow_html=True,
    )
    st.caption("TORONTO / MOBILITY RESEARCH LAB")
    st.title("Explore a city. Question a policy.")
    st.write("A transparent ride-hailing simulator for research and learning.")
    if "scenario" not in st.session_state:
        st.session_state.scenario = ScenarioConfig.from_source(
            ROOT / "configs/experiments/full_day.yaml"
        ).as_dict()
    if "engine" not in st.session_state:
        st.session_state.engine = create_engine(st.session_state.scenario)
    config = st.session_state.scenario
    st.caption(
        f"ACTIVE SCENARIO · {POLICY_NAMES[PolicyId(config['policy']['name'])]} · "
        f"{config['simulation']['fleet_size']} drivers · seed {config['project']['random_seed']} · "
        f"{config['simulation']['start_time']}–{config['simulation']['end_time']} · "
        f"{config['behavior']['profile']} behavior"
    )
    view = st.radio(
        "Workspace",
        ["Set up a scenario", "Explore the simulation", "Compare policies", "Understand the model"],
        index=1,
        horizontal=True,
        label_visibility="collapsed",
        key="workspace_view",
    )
    {
        "Set up a scenario": setup_view,
        "Explore the simulation": explore_view,
        "Compare policies": compare_view,
        "Understand the model": model_view,
    }[view]()


if __name__ == "__main__":
    main()
