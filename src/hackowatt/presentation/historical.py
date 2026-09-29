"""Polished historical-data dashboard renderer, isolated from simulation."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from ..simulation.behaviour import ACTIVITIES, PEOPLE


def render_historical_dashboard(source: dict) -> str:
    """Embed a prepared generated-data view model into the dashboard template."""
    hourly = source["hourly"]
    people = source["people"]
    energy = [column for column in hourly if column.endswith("_kwh") and column not in
              ("total_kwh", "hot_water_unmet_kwh", "thermal_residual_kwh")]
    payload = {
        "time": hourly.timestamp_local.tolist(), "energy_names": energy,
        "activities": ACTIVITIES, "people": {},
        "energy": hourly[energy].round(5).to_numpy().tolist(),
        "total": hourly.total_kwh.round(4).tolist(),
        "outdoor": hourly.temperature_2m.round(2).tolist(),
        "indoor": hourly.indoor_c.round(2).tolist(),
        "tank": hourly.tank_c.round(2).tolist(),
        "setpoint": hourly.setpoint_c.round(2).tolist(),
        "occupancy": hourly.occupancy_mean.round(3).tolist(),
        "family_vacation": hourly.family_vacation.astype(bool).tolist(),
        "night_ventilation": hourly.night_ventilation_active_fraction.round(3).tolist(),
        "comparison": source["comparison"].replace({np.nan: None}).to_dict("records"),
        "report": source["report"],
    }
    for person in PEOPLE:
        person_data = people[people.person == person]
        payload["people"][person] = {
            "minutes": person_data[[activity + "_minutes" for activity in ACTIVITIES]].to_numpy().tolist(),
            "home": person_data.home_minutes.tolist(),
        }
    template = (Path(__file__).resolve().parent / "assets" / "historical_dashboard.html").read_text(
        encoding="utf-8")
    return template.replace("/* EMBED_DATA */", "const D=" + json.dumps(
        payload, separators=(",", ":"), ensure_ascii=False) + ";")
