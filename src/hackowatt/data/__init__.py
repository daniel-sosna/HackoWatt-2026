"""Static JSON/CSV loading and generated-data repositories."""

from .generated import (load_generated_household, load_historical_dashboard_source,
                        load_thermal_dashboard_source, read_hourly)
from .loaders import (hashes, load_calendars, load_config, load_forecast_weather,
                      load_reference, load_weather, resolve_house)

__all__ = [
    "hashes", "load_calendars", "load_config", "load_generated_household", "load_historical_dashboard_source", "load_reference",
    "load_weather", "load_forecast_weather", "load_thermal_dashboard_source", "read_hourly", "resolve_house",
]
