"""Read-only view models for the unified Streamlit dashboard."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from ..analysis import peak_hours
from ..data import (load_forecast_artifacts, load_generated_household,
                    load_historical_dashboard_source, load_thermal_dashboard_source)
from ..optimisation import flexible_load_recommendations
from ..renewable import ECONOMIC_MODES, evaluate_pv


class DashboardService:
    """Single orchestration boundary consumed by the presentation layer."""

    def __init__(self, generated_directory: Path, forecast_directory: Path):
        self.generated_directory = Path(generated_directory)
        self.forecast_directory = Path(forecast_directory)
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

    def forecast(self):
        return load_forecast_artifacts(self.forecast_directory)

    def renewable_dashboard_source(self) -> dict:
        """Prepare inputs for the rich planner without coupling services to HTML."""
        household = self.historical()
        try:
            forecast = self.forecast()
        except FileNotFoundError:
            forecast = None
        return {
            "hourly": household.hourly,
            "events": household.appliance_events,
            "forecast_predictions": forecast.predictions if forecast else None,
            "forecast_metrics": forecast.metrics if forecast else None,
            "thermal_model": load_thermal_dashboard_source(self.generated_directory),
        }

    def renewable(self, capacity_kwp: float, specific_yield: float, economic_mode: str) -> dict:
        household = self.historical()
        return evaluate_pv(household.hourly, capacity_kwp, specific_yield, ECONOMIC_MODES[economic_mode])

    def flexible_loads(self) -> pd.DataFrame:
        return flexible_load_recommendations(self.historical().appliance_events)
