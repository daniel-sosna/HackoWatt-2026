"""Static JSON/CSV loading and generated-data repositories."""

from .generated import load_generated_household, read_hourly
from .forecast_results import load_forecast_artifacts
from .loaders import hashes, load_calendars, load_config, load_reference, load_weather, resolve_house

__all__ = [
    "hashes", "load_calendars", "load_config", "load_forecast_artifacts", "load_generated_household", "load_reference",
    "load_weather", "read_hourly", "resolve_house",
]
