"""Conservative, explainable candidates for future load-shifting optimisation."""
from __future__ import annotations

import pandas as pd

from ..renewable import learn_habit_constraints


def flexible_load_recommendations(events: pd.DataFrame) -> pd.DataFrame:
    """Expose observed unattended-cycle flexibility without moving any load."""
    learned = learn_habit_constraints(events)
    rows = []
    for device, rule in learned.items():
        if not rule["enabled_by_default"]:
            continue
        rows.append({
            "device": device,
            "events": rule["events"],
            "energy_kwh": rule["energy_kwh"],
            "observed_start_hour": rule["observed_start_median"],
            "maximum_shift_hours": rule["maximum_shift_hours"],
            "automation": rule["automation"],
        })
    return pd.DataFrame(rows).sort_values("energy_kwh", ascending=False) if rows else pd.DataFrame()
