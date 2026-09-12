"""Streamlit marketplace dashboard (skeleton)."""

from __future__ import annotations

import streamlit as st

from toronto_rideshare.config import load_config
from toronto_rideshare.experiments import run_experiment, save_experiment_result


def main() -> None:
    st.set_page_config(page_title="Toronto Rideshare Digital Twin", layout="wide")
    st.title("Toronto Ride-Hailing Marketplace Digital Twin")
    st.caption("Research prototype — not Uber/Lyft proprietary pricing")

    config_path = st.sidebar.text_input("Config path", "configs/baseline.yaml")
    fleet_size = st.sidebar.number_input("Fleet size", min_value=1, value=20)
    demand_mult = st.sidebar.slider("Demand multiplier", 0.5, 2.0, 1.0)

    if st.sidebar.button("Run simulation"):
        with st.spinner("Running..."):
            result = run_experiment(config_path)
            save_experiment_result(result, "results/dashboard_runs")
        st.success("Simulation complete")
        st.json(result)

    st.info(
        "Full map layers (drivers, demand heatmap, pricing zones) arrive in Tasks 29–33. "
        "Current view runs baseline experiment metrics."
    )


if __name__ == "__main__":
    main()
