"""The actual browser decision module and page handlers, exercised offline."""

import subprocess
from pathlib import Path


def test_dashboard_event_regressions() -> None:
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        ["node", "scripts/check_dashboard_ui.js"], cwd=root, capture_output=True, text=True
    )
    assert result.returncode == 0, result.stdout + result.stderr
