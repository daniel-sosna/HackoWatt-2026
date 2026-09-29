"""Thin orchestration services joining independent domain modules."""

from .dashboard import DashboardService
from .forecasting import run_forecast
from .generation import generate_historical

__all__ = ["DashboardService", "generate_historical", "run_forecast"]
