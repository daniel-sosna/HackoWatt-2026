"""Rich renewable-planning dashboard renderer with no business rules."""
from __future__ import annotations

import json
from pathlib import Path

from ..renewable import build_dashboard_data


def render_renewable_dashboard(source: dict) -> str:
    """Embed an already-prepared household view model in the retained UI."""
    data = build_dashboard_data(source["hourly"], source["events"])
    data["forecast"] = source.get("forecast", {
        "available": False,
        "reason": "Run an issue-date forecast from the Forecast view first.",
    })
    data["thermalModel"] = source["thermal_model"]
    assets = Path(__file__).resolve().parent / "assets" / "renewable"
    template = (assets / "renewable_dashboard.html").read_text(encoding="utf-8")
    for name in ("renewable_engine.js", "renewable_ui.js", "renewable_style.css"):
        template = template.replace(
            f"/* EMBED_{name} */", (assets / name).read_text(encoding="utf-8"))
    payload = json.dumps(data, separators=(",", ":"), ensure_ascii=False,
                         allow_nan=False).replace("<", "\\u003c")
    return template.replace("/* EMBED_DATA */", "const D=" + payload + ";")
