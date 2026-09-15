"""Interactive control room for the discrete Toronto marketplace simulator."""

from __future__ import annotations

import json
import os
from dataclasses import replace
from pathlib import Path

import pandas as pd
import streamlit as st

from toronto_rideshare.config import load_config
from toronto_rideshare.demand import generate_trips
from toronto_rideshare.experiments import (
    load_routing_context,
    run_repeated_policy_comparison,
)
from toronto_rideshare.policies.behavior import BehaviorConfig, OfferAcceptanceConfig
from toronto_rideshare.policies.registry import POLICY_REGISTRY, PolicyId
from toronto_rideshare.simulation import SimulationClock, SimulationEngine
from toronto_rideshare.supply import initialize_fleet
from toronto_rideshare.zones import (
    toronto_boundary_geojson,
    toronto_zone_cells,
    zone_boundary,
)


def _load_results(results_dir: Path) -> list[dict]:
    if not results_dir.is_dir():
        return []
    rows: list[dict] = []
    for path in sorted(results_dir.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if "results" in data:
                rows.extend(data["results"])
            else:
                rows.append(data)
        except (json.JSONDecodeError, OSError):
            continue
    return rows


@st.cache_data
def _zone_geometry() -> list[dict]:
    rows = []
    for zone in toronto_zone_cells():
        rows.append(
            {
                "zone": zone,
                "polygon": [[lon, lat] for lat, lon in zone_boundary(zone)],
            }
        )
    return rows


@st.cache_data
def _boundary_metadata() -> dict:
    return toronto_boundary_geojson()["metadata"]


@st.cache_resource(max_entries=8)
def _routing_context(config_path: str, use_time_dependent: bool):
    if os.getenv("TORONTO_RIDESHARE_DISABLE_ROUTING") == "1":
        return None
    config = load_config(config_path)
    context = load_routing_context(config)
    if context is not None:
        context = replace(context, use_time_dependent=use_time_dependent)
    return context


def _new_engine(settings: dict) -> SimulationEngine:
    zones = list(toronto_zone_cells())
    seed = settings["seed"]
    demand_multiplier = settings["demand_multiplier"]
    config = load_config(settings["config_path"])
    sim_cfg = config.get("simulation", {})
    start_time = _time_to_min(sim_cfg.get("start_time", "07:00"))
    end_time = _time_to_min(sim_cfg.get("end_time", "10:00"))
    trips = generate_trips(
        zones,
        n_trips=50,
        start_time_min=start_time,
        random_seed=seed,
        demand_multiplier=demand_multiplier,
    )
    drivers = initialize_fleet(zones, fleet_size=settings["fleet_size"], random_seed=seed)
    routing = _routing_context(settings["config_path"], settings["time_dependent"])
    return SimulationEngine(
        clock=SimulationClock(
            start_time_min=start_time,
            end_time_min=end_time,
            step_min=float(sim_cfg.get("decision_interval_minutes", 5.0)),
        ),
        drivers=drivers,
        trips=trips,
        routing=routing,
        policy_settings=POLICY_REGISTRY[PolicyId(settings["policy"])],
        policy_cfg={
            "max_rider_premium_cad": settings["rider_cap"],
            "max_driver_bonus_cad": settings["bonus_cap"],
            "subsidy_budget_cad": settings["subsidy_budget"],
            "fairness_bound_cad": settings["fairness_bound"],
        },
        behavior=BehaviorConfig(
            rider_price_elasticity=settings["rider_elasticity"],
            driver_bonus_elasticity=settings["driver_elasticity"],
            reposition_acceptance=settings["reposition_acceptance"],
        )
        if POLICY_REGISTRY[PolicyId(settings["policy"])].use_behavior
        else None,
        acceptance=OfferAcceptanceConfig(
            intercept=settings["acceptance_intercept"],
            earnings_per_cad=settings["earnings_weight"],
            pickup_minutes_penalty=settings["pickup_penalty"],
        ),
        random_seed=seed,
        matching_strategy=settings["matching_strategy"],
        max_wait_time_min=settings["max_wait"],
    )


def _clock_label(minutes: float) -> str:
    hour, minute = divmod(int(minutes), 60)
    return f"{hour % 24:02d}:{minute:02d}"


def _time_to_min(value: str) -> float:
    hour, minute = value.split(":")
    return int(hour) * 60 + int(minute)


def _settings_form() -> tuple[bool, dict]:
    with st.sidebar:
        st.header("Scenario controls")
        with st.form("scenario"):
            config_path = st.text_input("Config path", "configs/experiments/baseline_run.yaml")
            policy = st.selectbox(
                "Policy",
                list(PolicyId),
                format_func=lambda item: item.value,
            )
            seed = st.number_input("Seed", min_value=0, value=42, step=1)
            fleet_size = st.slider("Fleet size", 1, 200, 30)
            demand_multiplier = st.slider("Demand multiplier", 0.1, 4.0, 1.0, 0.1)
            st.caption("Driver acceptance assumptions")
            acceptance_intercept = st.slider("Baseline log-odds", -5.0, 5.0, 0.5, 0.1)
            earnings_weight = st.slider("Earnings weight / CAD", 0.0, 1.0, 0.1, 0.01)
            pickup_penalty = st.slider("Pickup penalty / minute", 0.0, 1.0, 0.18, 0.01)
            rider_elasticity = st.slider("Rider price elasticity", -1.0, 0.0, -0.3, 0.05)
            driver_elasticity = st.slider("Driver bonus elasticity", 0.0, 1.5, 0.4, 0.05)
            reposition_acceptance = st.slider(
                "Reposition acceptance", 0.0, 1.0, 0.7, 0.05
            )
            max_wait = st.number_input("Rider max wait (minutes)", 1.0, 120.0, 15.0)
            st.caption("Policy limits")
            rider_cap = st.number_input("Rider premium cap (CAD)", 0.0, 50.0, 5.0)
            bonus_cap = st.number_input("Driver bonus cap (CAD)", 0.0, 50.0, 12.0)
            subsidy_budget = st.number_input("Subsidy budget (CAD)", 0.0, 10000.0, 500.0)
            fairness_bound = st.number_input("Fairness bound (CAD)", 0.0, 50.0, 3.0)
            matching_strategy = st.selectbox(
                "Matching strategy", ["greedy", "optimal_batch"]
            )
            time_dependent = st.toggle("Time-dependent routing", value=True)
            submitted = st.form_submit_button("Initialize / reset", type="primary", width="stretch")
    return submitted, {
        "config_path": config_path,
        "policy": policy.value,
        "seed": int(seed),
        "fleet_size": fleet_size,
        "demand_multiplier": demand_multiplier,
        "acceptance_intercept": acceptance_intercept,
        "earnings_weight": earnings_weight,
        "pickup_penalty": pickup_penalty,
        "rider_elasticity": rider_elasticity,
        "driver_elasticity": driver_elasticity,
        "reposition_acceptance": reposition_acceptance,
        "max_wait": max_wait,
        "rider_cap": rider_cap,
        "bonus_cap": bonus_cap,
        "subsidy_budget": subsidy_budget,
        "fairness_bound": fairness_bound,
        "matching_strategy": matching_strategy,
        "time_dependent": time_dependent,
    }


def _render_map(engine: SimulationEngine) -> None:
    try:
        import pydeck as pdk
    except ImportError:
        st.warning("Install the visualization extra to render H3 polygons.")
        return

    snapshot = engine.last_snapshot
    zone_state = snapshot["zone_state"]
    policy_event = next(
        (e for e in reversed(engine.events) if e["type"] == "policy_decision"), None
    )
    adjustments = policy_event["zone_adjustments"] if policy_event else {}
    polygons = []
    for row in _zone_geometry():
        stats = zone_state.get(row["zone"], {})
        adjustment = adjustments.get(row["zone"], {})
        imbalance = float(stats.get("imbalance", 0.0))
        bonus = float(adjustment.get("driver_bonus", 0.0))
        premium = float(adjustment.get("rider_premium", 0.0))
        polygons.append(
            {
                **row,
                "imbalance": imbalance,
                "driver_bonus": bonus,
                "rider_premium": premium,
                "color": [
                    min(230, int(80 + max(0.0, imbalance) * 25)),
                    min(210, int(100 + bonus * 8)),
                    min(230, int(150 + max(0.0, -imbalance) * 20)),
                    100,
                ],
            }
        )

    request_points = []
    for trip in snapshot["pending_requests"]:
        request_points.extend(
            [
                {
                    "request_id": trip["request_id"],
                    "kind": "origin",
                    "lat": trip["origin_lat"],
                    "lon": trip["origin_lon"],
                    "color": [255, 170, 0, 210],
                },
                {
                    "request_id": trip["request_id"],
                    "kind": "destination",
                    "lat": trip["destination_lat"],
                    "lon": trip["destination_lon"],
                    "color": [120, 80, 220, 180],
                },
            ]
        )
    driver_colors = {
        "idle": [30, 180, 90, 230],
        "with_rider": [30, 110, 230, 230],
        "en_route_pickup": [255, 170, 0, 230],
        "repositioning": [160, 70, 200, 230],
    }
    drivers = [
        {**driver, "color": driver_colors[driver["status"]]} for driver in snapshot["drivers"]
    ]
    offers = [
        {
            **event,
            "lat": event["origin"][0],
            "lon": event["origin"][1],
            "color": [20, 190, 90, 240]
            if event["type"] == "offer_accepted"
            else [220, 45, 55, 240],
        }
        for event in snapshot["events"]
        if event["type"] in {"offer_accepted", "offer_rejected"}
    ]
    routes = [
        {
            **movement,
            "path": [
                [movement["origin"][1], movement["origin"][0]],
                [movement["destination"][1], movement["destination"][0]],
            ],
        }
        for movement in snapshot["active_movements"]
    ]
    layers = [
        pdk.Layer(
            "PolygonLayer",
            polygons,
            get_polygon="polygon",
            get_fill_color="color",
            get_line_color=[70, 80, 90, 100],
            line_width_min_pixels=0.5,
            pickable=True,
        ),
        pdk.Layer(
            "PathLayer",
            routes,
            get_path="path",
            get_color=[40, 110, 230, 190],
            get_width=4,
            width_min_pixels=2,
            pickable=True,
        ),
        pdk.Layer(
            "ScatterplotLayer",
            request_points,
            get_position="[lon, lat]",
            get_fill_color="color",
            get_radius=65,
            pickable=True,
        ),
        pdk.Layer(
            "ScatterplotLayer",
            drivers,
            get_position="[lon, lat]",
            get_fill_color="color",
            get_radius=100,
            stroked=True,
            get_line_color=[255, 255, 255],
            pickable=True,
        ),
        pdk.Layer(
            "ScatterplotLayer",
            offers,
            get_position="[lon, lat]",
            get_fill_color="color",
            get_radius=150,
            pickable=True,
        ),
    ]
    deck = pdk.Deck(
        layers=layers,
        initial_view_state=pdk.ViewState(latitude=43.70, longitude=-79.40, zoom=9.4, pitch=0),
        tooltip={
            "html": "<b>{zone}{driver_id}{request_id}</b><br/>"
            "state: {status}<br/>imbalance: {imbalance}<br/>"
            "premium: ${rider_premium}<br/>bonus: ${driver_bonus}"
        },
        map_style="light",
    )
    st.pydeck_chart(deck, width="stretch", height=620)


def main() -> None:
    st.set_page_config(page_title="Toronto Rideshare Digital Twin", layout="wide")
    st.title("Toronto marketplace control room")
    st.caption(
        "Synthetic demand and assumed acceptance behavior on a discrete 5-minute clock. "
        "Movement uses explicit pickup, with-rider, and repositioning phases with "
        "discrete endpoint updates; markers are not smooth GPS traces."
    )

    submitted, settings = _settings_form()
    if submitted or "engine" not in st.session_state:
        st.session_state.engine = _new_engine(settings)
        st.session_state.settings = settings
    engine: SimulationEngine = st.session_state.engine

    with st.container(horizontal=True):
        if st.button("Reset", icon=":material/restart_alt:", key="reset"):
            engine.reset()
        if st.button("Step", icon=":material/step_over:", type="primary", key="step"):
            engine.step()
        steps_per_refresh = st.number_input(
            "Steps per run", min_value=1, max_value=36, value=6, key="steps_per_refresh"
        )
        if st.button("Run bounded steps", icon=":material/play_arrow:", key="run_steps"):
            for _ in range(int(steps_per_refresh)):
                if engine.finished:
                    break
                engine.step()

    snapshot = engine.last_snapshot
    mode = snapshot["routing_mode"]
    if mode == "haversine fallback":
        st.warning(
            "Routing mode: haversine fallback (no configured local GraphML found). "
            f"Travel is a straight-line time proxy. Reason: "
            f"{snapshot['routing_fallback_reason']}."
        )
    else:
        st.success(f"Routing mode: {mode}")

    metrics = snapshot["metrics"]
    with st.container(horizontal=True):
        st.metric("Simulation time", _clock_label(snapshot["time_min"]), border=True)
        st.metric("Completed", metrics["completed_trips"], border=True)
        st.metric(
            "Pending / in progress / unserved",
            (
                f"{len(snapshot['pending_requests'])} / "
                f"{metrics['in_progress_trips']} / "
                f"{metrics['unserved_arrived_trips']}"
            ),
            border=True,
        )
        st.metric("Mean wait", f"{engine.waiting.mean_total_wait_min():.1f} min", border=True)
        st.metric("Rider payments", f"${metrics['total_rider_payment_cad']:.0f}", border=True)
        st.metric("Driver earnings", f"${metrics['total_driver_earnings_cad']:.0f}", border=True)
        st.metric("Rejections", metrics["rejected_offers"], border=True)
        st.metric(
            "Subsidy / optimizations",
            f"${metrics['subsidy_spend_cad']:.0f} / {metrics['optimization_steps']}",
            border=True,
        )

    left, right = st.columns([2.2, 1])
    with left:
        with st.container(border=True):
            st.subheader("Live marketplace")
            _render_map(engine)
            st.caption(
                "Hex color combines demand–supply imbalance and policy bonuses. "
                "Orange/purple = pending origins/destinations; green/red rings = "
                "accepted/rejected offers; driver color shows state."
            )
    with right:
        with st.container(border=True):
            st.subheader("Latest decision events")
            event_df = pd.DataFrame(snapshot["events"])
            st.dataframe(event_df, hide_index=True, height=300, width="stretch")
        with st.container(border=True):
            st.subheader("Zone state and policy")
            zone_df = pd.DataFrame.from_dict(snapshot["zone_state"], orient="index")
            zone_df.index.name = "zone"
            st.dataframe(
                zone_df.reset_index().sort_values("imbalance", ascending=False),
                hide_index=True,
                height=300,
                width="stretch",
            )

    with st.expander("Full event log"):
        st.dataframe(pd.DataFrame(engine.events), hide_index=True, width="stretch")

    with st.expander("Saved results and policy comparison", expanded=False):
        results_dir = st.text_input("Results directory", "results/experiments")
        results = _load_results(Path(results_dir))
        if results:
            st.dataframe(pd.DataFrame(results), hide_index=True, width="stretch")
        st.caption(
            "Comparisons use identical synthetic demand/fleet draws for every policy "
            "within each seed. Intervals describe simulation randomness, not calibration "
            "to observed Toronto outcomes."
        )
        with st.form("policy_comparison"):
            comparison_policies = st.multiselect(
                "Policies",
                list(PolicyId),
                default=list(PolicyId),
                format_func=lambda item: item.value,
                key="comparison_policies",
            )
            comparison_replicates = st.number_input(
                "Repeated seeds", 1, 30, 3, key="comparison_replicates"
            )
            run_comparison = st.form_submit_button(
                "Run policy comparison",
                icon=":material/compare_arrows:",
                type="primary",
                width="stretch",
            )
        if run_comparison and not comparison_policies:
            st.warning("Select at least one policy.")
        elif run_comparison:
            with st.status("Running common-seed policy comparisons...", expanded=True) as status:
                st.write(
                    f"{len(comparison_policies)} policies × "
                    f"{int(comparison_replicates)} seeds"
                )
                comparison = run_repeated_policy_comparison(
                    settings["config_path"],
                    policies=tuple(comparison_policies),
                    n_replicates=int(comparison_replicates),
                    base_seed=settings["seed"],
                    load_configured_routing=(
                        os.getenv("TORONTO_RIDESHARE_DISABLE_ROUTING") != "1"
                    ),
                )
                out = Path("results/dashboard_runs") / "policy_comparison.json"
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_text(json.dumps(comparison, indent=2), encoding="utf-8")
                st.session_state.comparison = comparison
                status.update(label="Policy comparison complete", state="complete")
        if "comparison" in st.session_state:
            comparison = st.session_state.comparison
            metric_options = list(comparison["aggregates"][0]["metrics"])
            selected_metric = st.selectbox(
                "Comparison metric", metric_options, key="comparison_metric"
            )
            rows = [
                {
                    "policy": aggregate["policy_id"],
                    "mean": aggregate["metrics"][selected_metric]["mean"],
                    "ci95_low": aggregate["metrics"][selected_metric]["ci95_low"],
                    "ci95_high": aggregate["metrics"][selected_metric]["ci95_high"],
                }
                for aggregate in comparison["aggregates"]
            ]
            comparison_df = pd.DataFrame(rows)
            baseline = comparison_df.iloc[0]["mean"]
            comparison_df["delta_vs_baseline"] = comparison_df["mean"] - baseline
            st.bar_chart(comparison_df, x="policy", y="mean")
            st.dataframe(
                comparison_df,
                hide_index=True,
                width="stretch",
                column_config={
                    "mean": st.column_config.NumberColumn("Mean", format="%.3f"),
                    "ci95_low": st.column_config.NumberColumn("95% CI low", format="%.3f"),
                    "ci95_high": st.column_config.NumberColumn(
                        "95% CI high", format="%.3f"
                    ),
                    "delta_vs_baseline": st.column_config.NumberColumn(
                        "Delta vs first policy", format="%+.3f"
                    ),
                },
            )
            zone_rows = []
            for replicate in comparison["replicates"]:
                for zone, values in replicate["zone_state"].items():
                    if (
                        values.get("demand", 0)
                        or values.get("supply", 0)
                        or values.get("rider_premium_cad", 0)
                        or values.get("driver_bonus_cad", 0)
                    ):
                        zone_rows.append(
                            {
                                "policy": replicate["policy_id"],
                                "seed": replicate["random_seed"],
                                "zone": zone,
                                **values,
                            }
                        )
            st.subheader("Per-zone policy outcomes")
            st.dataframe(
                pd.DataFrame(zone_rows),
                hide_index=True,
                width="stretch",
                height=320,
            )

    source = _boundary_metadata()
    st.caption(
        f"Boundary: {source['source']} (retrieved {source['retrieved']}); "
        "dissolved ward polygons, simplified for local display. "
        "Map data © OpenStreetMap contributors."
    )


if __name__ == "__main__":
    main()
