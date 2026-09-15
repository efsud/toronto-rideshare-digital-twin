"""Export the project big-picture summary to a Word document."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt

OUTPUT_PATH = Path("docs/Toronto_Rideshare_Digital_Twin_Big_Picture.docx")


def _add_table(doc: Document, headers: list[str], rows: list[list[str]]) -> None:
    table = doc.add_table(rows=1, cols=len(headers))
    table.style = "Table Grid"
    hdr_cells = table.rows[0].cells
    for i, header in enumerate(headers):
        hdr_cells[i].text = header
    for row in rows:
        cells = table.add_row().cells
        for i, value in enumerate(row):
            cells[i].text = value
    doc.add_paragraph()


def _add_code_block(doc: Document, text: str) -> None:
    paragraph = doc.add_paragraph()
    run = paragraph.add_run(text)
    run.font.name = "Courier New"
    run.font.size = Pt(9)


def build_document() -> Document:
    doc = Document()
    generated = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")

    title = doc.add_heading("Toronto Ride-Hailing Marketplace Digital Twin", level=0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    subtitle = doc.add_paragraph("v0.4 Big Picture Project Summary")
    subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_paragraph(f"Generated: {generated}")
    doc.add_paragraph(
        "Repository: toronto-rideshare-digital-twin | Branch: feature/traffic-layer | "
        "Draft PR: https://github.com/efsud/toronto-rideshare-digital-twin/pull/1"
    )
    doc.add_page_break()

    doc.add_heading("1. Ultimate Purpose", level=1)
    doc.add_paragraph(
        "This project is an independent research prototype of a ride-hailing marketplace "
        "in Toronto. It is not a copy of Uber or Lyft proprietary systems. The goal is to "
        "study how traffic, matching, two-sided pricing, driver incentives, and spatial "
        "supply-demand imbalance interact on Toronto's real street network."
    )
    doc.add_paragraph("End-state capabilities:")
    for item in [
        "Real Toronto road network with time-dependent travel times tau_e(t)",
        "Rider origins/destinations and driver fleet simulation",
        "Independent rider price adjustments a_z,t and driver bonuses b_z,t",
        "Policy optimization and fair comparison across scenarios",
        "Interactive dashboard for recruiters and research audiences",
    ]:
        doc.add_paragraph(item, style="List Bullet")

    doc.add_paragraph("Core trip-time equation:")
    _add_code_block(
        doc,
        "T_trip(r, t) = min over paths P from o_r to d_r  sum_{e in P} tau_e(t)",
    )

    doc.add_heading("2. What Has Been Done So Far", level=1)

    doc.add_heading("Layer 1 — Road Network (Tasks 01–02)", level=2)
    _add_table(
        doc,
        ["Component", "Location", "Status"],
        [
            ["OSM network download", "network/build_network.py", "Done"],
            ["Graph save/load", "data/processed/toronto_drive.graphml", "Done"],
            ["Shortest-path routing", "network/routing.py", "Done"],
            ["Route demo", "examples/route_demo.py", "Done"],
        ],
    )

    doc.add_heading("Layer 2 — Time-Dependent Traffic (Tasks 03–06)", level=2)
    _add_table(
        doc,
        ["Component", "Location", "Status"],
        [
            ["Traffic ingest", "traffic/ingest.py", "Done (baseline)"],
            ["Edge mapping", "traffic/map_to_edges.py", "Done (baseline)"],
            ["tau_e(t) profile", "traffic/travel_times.py", "Done (baseline)"],
            ["Time-dependent routing", "traffic/apply.py", "Done"],
            ["Route comparison demo", "examples/time_dependent_route_demo.py", "Done"],
            ["Route visualization", "examples/plot_time_dependent_routes.py", "Done"],
            ["Congestion map", "examples/plot_congestion_map.py", "Done"],
        ],
    )
    doc.add_paragraph(
        "Verified: same York University to City Hall trip shows different travel times "
        "at 07:00, 08:30, 12:00, and 17:00."
    )

    doc.add_heading("Layer 3 — Marketplace and policy engine", level=2)
    _add_table(
        doc,
        ["Component", "Location", "Maturity"],
        [
            ["H3 zoning", "zones/h3_zones.py", "Toronto boundary clipped"],
            ["Synthetic demand", "demand/generator.py", "Seeded intensity scaling"],
            ["Driver fleet", "supply/fleet.py", "Seeded"],
            ["Simulation engine", "simulation/engine.py", "Explicit movement phases"],
            ["Matching", "marketplace/matching.py", "Greedy + OR-Tools batch"],
            ["Two-sided fares", "marketplace/fares.py", "Explicit accounting"],
            ["Policies", "policies/", "P0–P7 registry"],
            ["Experiment runner", "experiments/runner.py", "YAML + metadata"],
            ["Streamlit dashboard", "dashboard/app.py", "Interactive control room"],
        ],
    )

    doc.add_heading("Infrastructure", level=2)
    for item in [
        "GitHub Actions CI (.github/workflows/ci.yml)",
        "artifacts/ task output convention",
        "Pytest suite with Streamlit AppTest and OR-Tools execution",
        "configs/scenarios/ and configs/experiments/",
        "scripts/task_00_validate_env.py and scripts/final_validation.py",
    ]:
        doc.add_paragraph(item, style="List Bullet")

    doc.add_heading("3. What Still Needs to Be Done", level=1)

    doc.add_heading("High Priority", level=2)
    for item in [
        "Ingest real Toronto Open Data traffic observations",
        "Calibrate behavioral response coefficients against defensible public evidence",
        "Validate policy outcomes over larger stochastic scenario sets",
    ]:
        doc.add_paragraph(item, style="List Number")

    doc.add_heading("Medium Priority", level=2)
    for item in [
        "Continuous route interpolation for presentation",
        "Larger-scale assignment performance benchmarking",
        "Real-data traffic coverage and freshness monitoring",
    ]:
        doc.add_paragraph(item, style="List Number")

    doc.add_heading("Lower Priority", level=2)
    for item in [
        "SUMO/TraCI microsimulation validation (see docs/SUMO.md)",
        "ML traffic and demand forecasting",
        "Optional RL benchmark after deterministic baselines",
        "Recruiter-grade README, demo GIF, portfolio assets",
    ]:
        doc.add_paragraph(item, style="List Number")

    doc.add_heading("4. Architecture Overview", level=1)
    _add_code_block(
        doc,
        "\n".join(
            [
                "OpenStreetMap",
                "    |",
                "    v",
                "network/  -->  GraphML  -->  routing (free-flow or travel_time_t)",
                "    |",
                "    v",
                "traffic/  -->  edge_traffic_profile.parquet",
                "    |",
                "    v",
                "zones/ (H3)  -->  demand/ + supply/",
                "    |",
                "    v",
                "marketplace/ (matching + fares)  -->  simulation/engine",
                "    |",
                "    v",
                "policies/ + optimization/  -->  experiments/  -->  dashboard/",
            ]
        ),
    )

    doc.add_heading("Module Inventory (src/toronto_rideshare/)", level=2)
    _add_table(
        doc,
        ["Package", "Role"],
        [
            ["network/", "Build graph, free-flow and weighted routing"],
            ["traffic/", "Ingest, map, tau_e(t), apply travel_time_t"],
            ["zones/", "H3 spatial cells for Toronto"],
            ["demand/", "Synthetic trip requests"],
            ["supply/", "Driver agents and fleet init"],
            ["marketplace/", "Matching and fare computation"],
            ["simulation/", "Clock, waiting times, engine"],
            ["policies/", "Rule-based pricing and repositioning"],
            ["optimization/", "Bounded OR-Tools pricing optimization"],
            ["experiments/", "YAML experiment runner"],
            ["config.py", "Load YAML configuration files"],
        ],
    )

    doc.add_heading("5. Progress Estimates", level=1)
    _add_table(
        doc,
        ["Area", "Completion vs Final Vision"],
        [
            ["Network + routing", "100%"],
            ["Time-dependent traffic", "80%"],
            ["Marketplace simulation", "75%"],
            ["OR-Tools optimization", "65%"],
            ["Dashboard + visualization", "75%"],
            ["Policy comparison", "75%"],
            ["SUMO / RL / advanced ML", "0% (planned only)"],
        ],
    )

    doc.add_heading("6. How to Run", level=1)
    _add_code_block(
        doc,
        "\n".join(
            [
                "source .venv/bin/activate",
                "pip install -e \".[dev,visualization,optimization]\"",
                "",
                "# Network + traffic",
                "python examples/download_toronto_network.py",
                "python examples/build_traffic_profile.py",
                "python examples/time_dependent_route_demo.py",
                "python examples/plot_time_dependent_routes.py",
                "python examples/plot_congestion_map.py",
                "",
                "# Marketplace",
                "python examples/run_baseline_experiment.py",
                "streamlit run dashboard/app.py",
                "",
                "# Validation",
                "pytest",
                "python scripts/task_00_validate_env.py",
                "python scripts/final_validation.py",
            ]
        ),
    )

    doc.add_heading("7. Artifacts and Outputs", level=1)
    _add_table(
        doc,
        ["Path", "Description"],
        [
            ["figures/time_dependent_routes_york_to_cityhall.png", "4 departure times route plot"],
            ["artifacts/task_05_congestion/", "Congestion ratio maps"],
            ["artifacts/task_00_env/", "Environment validation report"],
            ["results/experiments/", "JSON experiment metrics"],
            ["data/processed/edge_traffic_profile.parquet", "Edge-level tau_e(t)"],
        ],
    )

    doc.add_heading("8. Data Policy and Limitations", level=1)
    doc.add_paragraph(
        "Road network data come from OpenStreetMap (observed, public). Default traffic demo "
        "uses synthetic observations. Future rider OD data will be synthetic and documented "
        "as such unless empirically estimated from public sources."
    )
    doc.add_paragraph("Current limitations:")
    for item in [
        "Sparse synthetic traffic; many edges use fallback speeds",
        "Haversine is used only when no usable network route is available",
        "Behavior coefficients are explicit assumptions, not causal estimates",
        "Movement uses discrete endpoints rather than continuous interpolation",
        "Edge costs frozen at trip departure (no within-trip dynamic routing)",
    ]:
        doc.add_paragraph(item, style="List Bullet")

    doc.add_heading("9. Git and Pull Request Status", level=1)
    doc.add_paragraph("Branch: feature/traffic-layer")
    doc.add_paragraph("Base: main")
    doc.add_paragraph("Draft PR #1: feat: time-dependent traffic layer and marketplace baseline")
    doc.add_paragraph("Key commits:")
    for item in [
        "18721bb — feat(traffic): time-dependent edge travel times and repo validation",
        "7c1ee9b — feat: marketplace baseline, H3 zones, and experiment runner",
    ]:
        doc.add_paragraph(item, style="List Bullet")

    return doc


def main() -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    document = build_document()
    document.save(OUTPUT_PATH)
    print(f"Wrote {OUTPUT_PATH.resolve()}")


if __name__ == "__main__":
    main()
