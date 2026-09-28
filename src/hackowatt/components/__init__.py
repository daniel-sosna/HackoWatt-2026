"""Built-in application components. Add a module and register it here."""
from .base import ComponentRegistry
from .historical_data import HistoricalDashboardComponent, HistoricalDataComponent
from .issue_date_forecast import IssueDateForecastComponent


def built_in_registry() -> ComponentRegistry:
    registry = ComponentRegistry()
    registry.register(HistoricalDataComponent())
    registry.register(HistoricalDashboardComponent())
    registry.register(IssueDateForecastComponent())
    return registry
