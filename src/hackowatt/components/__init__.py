"""Built-in application components. Add a module and register it here."""
from .base import ComponentRegistry
from .dashboard import DashboardComponent
from .historical_data import HistoricalDataComponent
from .issue_date_forecast import IssueDateForecastComponent


def built_in_registry() -> ComponentRegistry:
    registry = ComponentRegistry()
    registry.register(HistoricalDataComponent())
    registry.register(IssueDateForecastComponent())
    registry.register(DashboardComponent())
    return registry
