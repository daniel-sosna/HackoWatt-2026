"""Thin orchestration services joining independent domain modules."""

from .dashboard import DashboardService
from .forecasting import run_forecast
from .generation import generate_historical
from .weather_forecast import fetch_weather_forecast

__all__ = ["DashboardService", "fetch_weather_forecast", "generate_historical", "run_forecast"]
