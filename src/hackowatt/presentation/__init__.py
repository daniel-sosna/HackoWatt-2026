"""Presentation renderers and visual assets with no business rules."""

from .historical import render_historical_dashboard
from .forecast import render_forecast_dashboard
from .renewable import render_renewable_dashboard

__all__ = ["render_forecast_dashboard", "render_historical_dashboard", "render_renewable_dashboard"]
