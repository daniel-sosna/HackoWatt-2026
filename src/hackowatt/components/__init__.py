"""Built-in application components. Add a module and register it here."""
from .base import ComponentRegistry
from .dashboard import DashboardComponent
from .historical_data import HistoricalDataComponent
from .load_forecasting import LoadForecastComponent
from .weather_forecast import WeatherForecastComponent


def built_in_registry() -> ComponentRegistry:
    registry = ComponentRegistry()
    registry.register(HistoricalDataComponent())
    registry.register(LoadForecastComponent())
    registry.register(WeatherForecastComponent())
    registry.register(DashboardComponent())
    return registry
