"""Built-in application components. Add a module and register it here."""
from .base import ComponentRegistry
from .forecast_dashboard import ForecastDashboardComponent
from .historical_data import HistoricalDashboardComponent, HistoricalDataComponent
from .load_forecasting import LoadForecastComponent
from .model_benchmark import ModelBenchmarkComponent
from .selected_prediction import SelectedPredictionComponent


def built_in_registry() -> ComponentRegistry:
    registry = ComponentRegistry()
    registry.register(HistoricalDataComponent())
    registry.register(HistoricalDashboardComponent())
    registry.register(LoadForecastComponent())
    registry.register(ForecastDashboardComponent())
    registry.register(ModelBenchmarkComponent())
    registry.register(SelectedPredictionComponent())
    return registry
