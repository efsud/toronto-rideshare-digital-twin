"""Generate Task 00 environment validation report."""

from __future__ import annotations

import platform
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

REPORT_PATH = Path("artifacts/task_00_env/validation_report.md")


def _run(cmd: list[str]) -> str:
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    output = (result.stdout or "") + (result.stderr or "")
    status = "PASS" if result.returncode == 0 else "FAIL"
    return f"exit={result.returncode} ({status})\n```\n{output.strip()}\n```"


def main() -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Task 00 — Environment Validation Report",
        "",
        f"Generated: {datetime.now(UTC).isoformat()}",
        "",
        "## Python",
        f"- Version: `{sys.version.split()[0]}`",
        f"- Executable: `{sys.executable}`",
        f"- Platform: `{platform.platform()}`",
        "",
        "## pytest",
        _run([sys.executable, "-m", "pytest", "-q"]),
        "",
        "## ruff",
        _run([sys.executable, "-m", "ruff", "check", "src", "tests", "examples"]),
        "",
        "## Package import",
    ]
    try:
        import toronto_rideshare  # noqa: F401
        import toronto_rideshare.network  # noqa: F401
        import toronto_rideshare.traffic  # noqa: F401

        lines.append("- `toronto_rideshare` imports: **PASS**")
    except Exception as exc:
        lines.append(f"- `toronto_rideshare` imports: **FAIL** — {exc}")

    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {REPORT_PATH.resolve()}")


if __name__ == "__main__":
    main()
