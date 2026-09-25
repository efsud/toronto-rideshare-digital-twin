from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = Path(__file__).parents[1] / "dashboard/app.py"


def test_dashboard_starts_steps_resets_and_has_map():
    at = AppTest.from_file(str(APP), default_timeout=30).run()
    assert not at.exception
    assert at.title[0].value == "Explore a city. Question a policy."
    engine = at.session_state["engine"]
    assert '"characterSet": "auto"' in at.get("deck_gl_json_chart")[0].proto.json
    at.button(key="step").click().run()
    assert not at.exception
    assert at.session_state["engine"] is engine
    assert engine.last_snapshot["processed_time_min"] == 5
    at.button(key="reset").click().run()
    assert engine.clock.current_time_min == 0


def test_comparison_uses_applied_scenario():
    at = AppTest.from_file(str(APP), default_timeout=30).run()
    at.radio(key="workspace_view").set_value("Compare policies").run()
    assert len(at.multiselect(key="comparison_policies").options) == 3
    at.multiselect(key="comparison_policies").set_value(["P0_fixed_baseline"])
    at.number_input(key="comparison_replicates").set_value(1)
    next(b for b in at.button if b.label == "Run policy comparison").click().run()
    assert not at.exception
    result = at.session_state["comparison"]
    assert result["replicates"][0]["manifest"]["scenario"] == at.session_state["scenario"]
    assert at.dataframe


def test_setup_and_model_pages():
    at = AppTest.from_file(str(APP), default_timeout=30).run()
    at.radio(key="workspace_view").set_value("Set up a scenario").run()
    assert not at.exception
    fleet = next(x for x in at.number_input if x.label == "Drivers in the fleet")
    fleet.set_value(7).run()
    assert at.session_state["scenario"]["simulation"]["fleet_size"] == 60
    next(b for b in at.button if b.label == "Apply scenario and start fresh").click().run()
    assert not at.exception
    assert len(at.session_state["engine"].drivers) == 7
    at.radio(key="workspace_view").set_value("Understand the model").run()
    assert not at.exception
    assert at.dataframe


def test_full_day_preset_and_run_control():
    at = AppTest.from_file(str(APP), default_timeout=30).run()
    at.radio(key="workspace_view").set_value("Set up a scenario").run()
    next(b for b in at.button if b.label == "Load full-day adaptive-demand scenario").click().run()
    assert not at.exception
    assert at.session_state["scenario"]["simulation"]["end_time"] == "24:00"
    at.radio(key="workspace_view").set_value("Explore the simulation").run()
    next(b for b in at.button if b.label == "Run to end of day / scenario").click().run()
    assert not at.exception
    assert at.session_state["engine"].finished
    assert at.session_state["engine"].last_snapshot["processed_time_min"] == 1440
