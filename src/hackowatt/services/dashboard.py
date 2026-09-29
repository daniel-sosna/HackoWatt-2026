"""Read-only view models for the unified Streamlit dashboard."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from ..analysis import peak_hours, top_forecast_peaks
from ..data import (load_generated_household, load_historical_dashboard_source,
                    load_thermal_dashboard_source)
from ..optimisation import flexible_load_recommendations
from ..renewable import ECONOMIC_MODES, evaluate_pv, local_tariff


class DashboardService:
    """Single orchestration boundary consumed by the presentation layer."""

    def __init__(self, generated_directory: Path):
        self.generated_directory = Path(generated_directory)
        self._household_data = None

    def historical(self):
        if self._household_data is None:
            self._household_data = load_generated_household(self.generated_directory)
        return self._household_data

    def historical_summary(self) -> dict:
        household = self.historical()
        hourly = household.hourly
        return {
            "hours": len(hourly),
            "total_kwh": float(hourly.total_kwh.sum()),
            "mean_kwh": float(hourly.total_kwh.mean()),
            "peak_kw": float(hourly.peak_1min_kw.max()),
            "peaks": peak_hours(hourly),
        }

    def historical_dashboard_source(self) -> dict:
        """Return the validated data needed by the historical presentation."""
        return load_historical_dashboard_source(self.generated_directory)

    def forecast_dashboard_source(self, result, tariff_mode: str = "hackathon") -> dict:
        """Prepare the selected forecast, tariff series, and daily peak summary."""
        if tariff_mode not in ECONOMIC_MODES:
            raise ValueError(f"Unknown tariff mode: {tariff_mode}")
        forecast = result.forecast.copy()
        timestamps = pd.DatetimeIndex(pd.to_datetime(forecast["timestamp_utc"], utc=True))
        mode = ECONOMIC_MODES[tariff_mode]
        tariff = local_tariff(timestamps, mode)
        forecast["window"] = range(len(forecast))
        forecast["window"] //= 24
        forecast["tariff_price"] = tariff
        forecast["forecast_cost"] = forecast["forecast_kwh"] * tariff
        daily_costs = forecast.groupby("window", sort=True).agg(
            start_local=("timestamp_local", "first"),
            forecast_cost=("forecast_cost", "sum"),
        ).reset_index()
        return {
            "timestamps": forecast["timestamp_local"].tolist(),
            "forecast_kwh": forecast["forecast_kwh"].round(4).tolist(),
            "tariff_price": tariff.round(4).tolist(),
            "currency": mode.currency,
            "tariff_label": mode.label,
            "model": result.model_id.replace("_", " ").title(),
            "horizon": result.manifest["horizon_hours"],
            "weather": result.manifest["forecast_weather_source"],
            "peaks": top_forecast_peaks(forecast).to_dict("records"),
            "daily_costs": daily_costs.to_dict("records"),
        }

    def renewable_dashboard_source(self) -> dict:
        """Prepare inputs for the rich planner without coupling services to HTML."""
        household = self.historical()
        return {
            "hourly": household.hourly,
            "events": household.appliance_events,
            "thermal_model": load_thermal_dashboard_source(self.generated_directory),
        }

    def renewable(self, capacity_kwp: float, specific_yield: float, economic_mode: str) -> dict:
        household = self.historical()
        return evaluate_pv(household.hourly, capacity_kwp, specific_yield, ECONOMIC_MODES[economic_mode])

    def flexible_loads(self) -> pd.DataFrame:
        return flexible_load_recommendations(self.historical().appliance_events)
