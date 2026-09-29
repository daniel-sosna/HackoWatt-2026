"""Load analysis that is reusable by the dashboard and future recommendations."""
from __future__ import annotations

import pandas as pd


def peak_hours(hourly: pd.DataFrame, count: int = 10) -> pd.DataFrame:
    """Return the highest physical-hour loads with local timestamps and drivers."""
    if count <= 0:
        raise ValueError("count must be positive")
    required = {"timestamp_utc", "total_kwh"}
    if not required.issubset(hourly):
        raise ValueError(f"hourly data requires columns {sorted(required)}")
    result = hourly.nlargest(count, "total_kwh").copy()
    timestamp = pd.to_datetime(result["timestamp_utc"], utc=True)
    # Generated files already carry a local label; adapters may not.
    result["timestamp_local"] = timestamp.dt.tz_convert("Europe/Warsaw").astype(str)
    components = [
        column for column in ("space_heating_kwh", "water_heater_kwh", "cooking_kwh")
        if column in result
    ]
    result["dominant_known_load"] = (
        result[components].idxmax(axis=1).str.removesuffix("_kwh") if components else "unclassified"
    )
    return result[["timestamp_utc", "timestamp_local", "total_kwh", "dominant_known_load", *components]]
