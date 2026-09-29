"""Peak selection for issued load forecasts."""
from __future__ import annotations

import numpy as np
import pandas as pd


def top_forecast_peaks(forecast: pd.DataFrame, count_per_day: int = 2) -> pd.DataFrame:
    """Return the largest predicted loads in each consecutive 24-hour window."""
    if count_per_day <= 0:
        raise ValueError("count_per_day must be positive")
    required = {"timestamp_utc", "forecast_kwh"}
    if not required.issubset(forecast):
        raise ValueError(f"forecast requires columns {sorted(required)}")
    result = forecast[["timestamp_utc", "forecast_kwh"]].copy()
    timestamp = pd.to_datetime(result["timestamp_utc"], utc=True, errors="raise")
    if timestamp.duplicated().any() or not timestamp.is_monotonic_increasing:
        raise ValueError("forecast timestamps must be sorted and unique")
    result["window"] = np.arange(len(result)) // 24
    result["timestamp_local"] = timestamp.dt.tz_convert("Europe/Warsaw").astype(str)
    result["peak_rank"] = result.groupby("window")["forecast_kwh"].rank(
        method="first", ascending=False)
    result = result[result["peak_rank"] <= count_per_day]
    return result.sort_values(["window", "forecast_kwh"], ascending=[True, False]).reset_index(drop=True)
