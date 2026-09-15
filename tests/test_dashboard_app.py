import os
from pathlib import Path

from streamlit.testing.v1 import AppTest

from toronto_rideshare.policies.registry import PolicyId

os.environ["TORONTO_RIDESHARE_DISABLE_ROUTING"] = "1"

APP = Path(__file__).parents[1] / "dashboard" / "app.py"


def test_dashboard_starts_and_steps_same_engine() -> None:
    at = AppTest.from_file(str(APP), default_timeout=20).run()
    assert not at.exception
    assert at.title[0].value == "Toronto marketplace control room"
    initial_engine = at.session_state["engine"]

    at.button(key="step").click().run()
    assert not at.exception
    assert at.session_state["engine"] is initial_engine
    assert at.session_state["engine"].clock.current_time_min == 425.0


def test_dashboard_reset_control() -> None:
    at = AppTest.from_file(str(APP), default_timeout=20).run()
    at.button(key="step").click().run()
    at.button(key="reset").click().run()
    assert not at.exception
    assert at.session_state["engine"].clock.current_time_min == 420.0


def test_dashboard_shows_fallback_map_and_policy_comparison() -> None:
    at = AppTest.from_file(str(APP), default_timeout=30).run()
    assert not at.exception
    assert any("haversine fallback" in warning.value for warning in at.warning)
    assert at.get("deck_gl_json_chart")

    at.multiselect(key="comparison_policies").set_value([PolicyId.P0])
    at.number_input(key="comparison_replicates").set_value(1)
    submit = next(button for button in at.button if button.label == "Run policy comparison")
    submit.click().run(timeout=30)

    assert not at.exception
    assert "comparison" in at.session_state
    assert at.selectbox(key="comparison_metric")
    assert at.dataframe
