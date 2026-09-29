"""Application service for downloading issued weather forecasts."""
from __future__ import annotations

from pathlib import Path

from ..weather import OpenMeteoForecastProvider


def fetch_weather_forecast(output_path: Path, forecast_days: int = 7) -> Path:
    """Fetch Silesia weather from Open-Meteo and save its canonical CSV."""
    return OpenMeteoForecastProvider(forecast_days).save_csv(Path(output_path))
