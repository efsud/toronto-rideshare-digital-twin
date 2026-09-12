"""Streamlit marketplace dashboard with map layers and experiment results."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st

from toronto_rideshare.experiments import (
    run_experiment,
    run_policy_comparison,
    save_experiment_result,
)
from toronto_rideshare.zones import toronto_zone_cells, zone_center


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


def _zone_map_df() -> pd.DataFrame:
    zones = sorted(toronto_zone_cells())[:80]
    rows = []
    for z in zones:
        lat, lon = zone_center(z)
        rows.append({"zone": z, "lat": lat, "lon": lon})
    return pd.DataFrame(rows)


def main() -> None:
    st.set_page_config(page_title="Toronto Rideshare Digital Twin", layout="wide")
    st.title("Toronto Ride-Hailing Marketplace Digital Twin")
    st.caption("Research prototype — not Uber/Lyft proprietary pricing")

    config_path = st.sidebar.text_input("Config path", "configs/experiments/baseline_run.yaml")
    results_dir = st.sidebar.text_input("Results directory", "results/experiments")

    tab_run, tab_results, tab_map = st.tabs(["Run", "Results", "Zone map"])

    with tab_run:
        if st.button("Run baseline simulation"):
            with st.spinner("Running..."):
                result = run_experiment(config_path)
                save_experiment_result(result, "results/dashboard_runs")
            st.success("Simulation complete")
            st.json(result)

        if st.button("Run P0–P7 policy comparison"):
            with st.spinner("Running all policies..."):
                comparison = run_policy_comparison(config_path)
                out = Path("results/dashboard_runs") / "policy_comparison.json"
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_text(json.dumps(comparison, indent=2), encoding="utf-8")
            st.success(f"Saved comparison to {out}")
            df = pd.DataFrame(
                [
                    {
                        "policy": r["policy_id"],
                        "completed_trips": r["metrics"]["completed_trips"],
                        "mean_wait_min": r["mean_wait_min"],
                        "network_routing": r.get("used_network_routing", False),
                    }
                    for r in comparison["results"]
                ]
            )
            st.dataframe(df)
            st.bar_chart(df.set_index("policy")["completed_trips"])

    with tab_results:
        results = _load_results(Path(results_dir))
        if not results:
            st.info(f"No JSON results found in {results_dir}. Run an experiment first.")
        else:
            df = pd.DataFrame(
                [
                    {
                        "policy": r.get("policy_id", r.get("policy", "unknown")),
                        "seed": r.get("random_seed"),
                        "completed": r["metrics"]["completed_trips"],
                        "unserved": r["metrics"]["unserved_trips"],
                        "mean_wait_min": r.get("mean_wait_min", 0),
                    }
                    for r in results
                ]
            )
            st.dataframe(df)
            if "policy" in df.columns and df["policy"].nunique() > 1:
                st.bar_chart(df.groupby("policy")["completed"].mean())
            st.line_chart(df["mean_wait_min"])

    with tab_map:
        zone_df = _zone_map_df()
        st.subheader("H3 zone centers (Toronto subset)")
        try:
            import pydeck as pdk

            layer = pdk.Layer(
                "ScatterplotLayer",
                data=zone_df,
                get_position="[lon, lat]",
                get_radius=200,
                get_fill_color=[0, 128, 255, 160],
                pickable=True,
            )
            view = pdk.ViewState(latitude=43.65, longitude=-79.38, zoom=10)
            st.pydeck_chart(pdk.Deck(layers=[layer], initial_view_state=view))
        except ImportError:
            st.scatter_chart(zone_df, x="lon", y="lat")
            st.caption("Install pydeck: pip install -e '.[visualization]'")

        try:
            import plotly.express as px

            fig = px.scatter_mapbox(
                zone_df,
                lat="lat",
                lon="lon",
                hover_name="zone",
                zoom=10,
                mapbox_style="open-street-map",
                title="Zone centers",
            )
            st.plotly_chart(fig, use_container_width=True)
        except ImportError:
            pass


if __name__ == "__main__":
    main()
