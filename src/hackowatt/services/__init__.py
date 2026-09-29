"""Thin orchestration services joining independent domain modules."""

from .dashboard import DashboardService
from .generation import generate_historical

__all__ = ["DashboardService", "generate_historical"]
