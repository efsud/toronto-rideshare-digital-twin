"""Guided research workspace. Synthetic evidence is always labeled."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pydeck as pdk
import streamlit as st

from toronto_rideshare.experiments.runner import create_engine, run_repeated_policy_comparison
from toronto_rideshare.manifest import METRIC_DEFINITIONS, run_manifest
from toronto_rideshare.policies.registry import PolicyId
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


def clock_label(minutes):
    return f"{int(minutes) // 60:02d}:{int(minutes) % 60:02d}"


def setup_view():
    st.subheader("Set up a scenario")
    st.caption("Change one assumption at a time. Applying changes creates a fresh run.")
    config = ScenarioConfig.from_source(st.session_state.scenario).as_dict()
    sim, policy, network = config["simulation"], config["policy"], config["network"]
    a, b = st.columns(2)
    with a:
        policy["name"] = st.selectbox(
            "Policy",
            list(PolicyId),
            index=list(PolicyId).index(PolicyId(policy["name"])),
            format_func=lambda p: POLICY_NAMES[p],
            key="scenario_policy",
        )
        sim["fleet_size"] = st.number_input("Drivers in the fleet", 0, 200, sim["fleet_size"])
        sim["base_trip_count"] = st.number_input(
            "Potential requests", 0, 2000, sim["base_trip_count"]
        )
        sim["demand_multiplier"] = st.number_input(
            "Demand multiplier", 0.0, 4.0, float(sim["demand_multiplier"]), 0.1
        )
    with b:
        sim["start_time"] = st.text_input("Start time · Toronto local time", sim["start_time"])
        sim["end_time"] = st.text_input("End time · same day", sim["end_time"])
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
    with st.expander("Behavior, pricing and matching assumptions"):
        options = ["policy_default", "greedy", "optimal_batch"]
        policy["matching_strategy"] = st.selectbox(
            "Matching strategy",
            options,
            index=options.index(policy["matching_strategy"]),
            format_func=lambda x: {
                "policy_default": "Use policy default",
                "greedy": "Nearest-driver greedy",
                "optimal_batch": "Optimal batch (custom override)",
            }[x],
        )
        config["behavior"]["profile"] = st.selectbox(
            "Behavior profile",
            ["shared", "legacy_v0.4"],
            index=["shared", "legacy_v0.4"].index(config["behavior"]["profile"]),
            format_func=lambda x: (
                "Same assumptions across policies" if x == "shared" else "Legacy v0.4 behavior"
            ),
        )
        config["behavior"]["additional_bonus_response"] = st.checkbox(
            "Additional bonus response (experimental)",
            config["behavior"]["additional_bonus_response"],
            help="Default off: gross earnings already include the bonus.",
        )
        fields = [
            ("rider_price_elasticity", "Rider price response coefficient", -10.0, 0.0),
            ("driver_bonus_elasticity", "Additional bonus response coefficient", 0.0, 10.0),
            ("reposition_acceptance", "Reposition acceptance probability", 0.0, 1.0),
            ("acceptance_intercept", "Driver acceptance intercept (log-odds)", -40.0, 40.0),
            ("acceptance_earnings_per_cad", "Driver earnings response (per CAD)", 0.0, 10.0),
            ("acceptance_pickup_minutes_penalty", "Pickup burden response (per minute)", 0.0, 10.0),
            ("max_rider_premium_cad", "Rider adjustment cap (CAD)", 0.0, 50.0),
            ("max_driver_bonus_cad", "Driver bonus cap (CAD)", 0.0, 50.0),
            ("subsidy_budget_cad", "Total subsidy budget (CAD)", 0.0, 10000.0),
            ("fairness_bound_cad", "Maximum cross-zone adjustment difference (CAD)", 0.0, 50.0),
            ("predicted_demand_response_per_cad", "LP demand response proxy (per CAD)", 0.0, 1.0),
            ("predicted_supply_response_per_cad", "LP supply response proxy (per CAD)", 0.0, 1.0),
        ]
        cols = st.columns(2)
        for i, (key, label, low, high) in enumerate(fields):
            policy[key] = cols[i % 2].number_input(label, low, high, float(policy[key]))
        sim["rider_max_wait_minutes"] = st.number_input(
            "Maximum unassigned queue wait (minutes)",
            0.25,
            120.0,
            float(sim["rider_max_wait_minutes"]),
        )
        st.caption(
            "Base fare: $3.50 + $1.10/km + $0.35/occupied minute. Driver "
            "gross share: 75%. Assumed, not Uber/Lyft prices."
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
            "**✓ / ×** Accepted / rejected offer, latest step only\n\n"
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
        list(PolicyId),
        default=list(PolicyId),
        format_func=lambda p: POLICY_NAMES[p],
        key="comparison_policies",
    )
    n = st.number_input(
        "Paired seeds · 3 for preview, 30 for research", 1, 100, 30, key="comparison_replicates"
    )
    controlled = st.selectbox(
        "Comparison design",
        ["Policy-specific matching", "Hold greedy matching fixed", "Hold optimal batch fixed"],
    )
    if st.button("Run policy comparison", type="primary"):
        config = ScenarioConfig.from_source(st.session_state.scenario).as_dict()
        config["policy"]["matching_strategy"] = {
            "Policy-specific matching": "policy_default",
            "Hold greedy matching fixed": "greedy",
            "Hold optimal batch fixed": "optimal_batch",
        }[controlled]
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
        "Outcome", list(result["aggregates"][0]["metrics"]), key="comparison_metric"
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
    handbook = ROOT / "docs" / "MODEL_HANDBOOK.md"
    if handbook.exists():
        st.markdown(handbook.read_text())
    st.subheader("Data and validation evidence")
    st.write(
        "Roads: OpenStreetMap when loaded. Demand: synthetic. Behavior: "
        "assumed. Traffic does not respond to the simulated fleet."
    )
    st.json(toronto_boundary_geojson()["metadata"], expanded=False)
    for name in ("PUBLIC_DATA_REPORT.md", "RELEASE_READINESS.md"):
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
            ROOT / "configs/experiments/baseline_run.yaml"
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
