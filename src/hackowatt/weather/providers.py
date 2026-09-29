"""Provider boundary for weather used by simulation and forecasting."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Protocol
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import numpy as np
import pandas as pd

from ..data import load_weather


OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
SILESIA_LATITUDE = 50.2649
SILESIA_LONGITUDE = 19.0238
OPEN_METEO_VARIABLES = {
    "temperature_2m": "temperature_2m_C",
    "relative_humidity_2m": "relative_humidity_2m_pct",
    "wind_speed_10m": "wind_speed_10m_kmh",
    "cloud_cover": "cloud_cover_pct",
    "snowfall": "snowfall_cm",
    "shortwave_radiation": "shortwave_radiation_wm2",
}
WEATHER_CSV_COLUMNS = ["time", *OPEN_METEO_VARIABLES.values()]


class WeatherProvider(Protocol):
    """Returns validated canonical hourly weather and its source audit."""

    def historical(self, configuration: dict) -> tuple[pd.DataFrame, dict]: ...


class CsvWeatherProvider:
    """Current static-file provider; replace this class for a real provider later."""

    def __init__(self, csv_path: Path):
        self.csv_path = Path(csv_path)

    def historical(self, configuration: dict) -> tuple[pd.DataFrame, dict]:
        return load_weather(self.csv_path, configuration)


class OpenMeteoForecastProvider:
    """Fetches a future Silesia weather forecast without changing historical inputs."""

    def __init__(self, forecast_days: int = 7):
        if not 1 <= forecast_days <= 16:
            raise ValueError("forecast_days must be between 1 and 16")
        self.forecast_days = forecast_days

    @staticmethod
    def parse_response(payload: dict, issue_time_utc: str) -> pd.DataFrame:
        """Validate and convert the Open-Meteo response to the project CSV schema."""
        hourly = payload.get("hourly")
        if not isinstance(hourly, dict):
            raise ValueError("Open-Meteo response is missing hourly forecast data")

        times = hourly.get("time")
        if not isinstance(times, list) or not times:
            raise ValueError("Open-Meteo response contains no hourly timestamps")
        frame = pd.DataFrame({"time": times})
        for source_name, output_name in OPEN_METEO_VARIABLES.items():
            values = hourly.get(source_name)
            if not isinstance(values, list) or len(values) != len(times):
                raise ValueError(f"Open-Meteo response has invalid hourly data for {source_name}")
            frame[output_name] = pd.to_numeric(pd.Series(values), errors="raise")

        labels = pd.DatetimeIndex(pd.to_datetime(frame["time"], errors="raise", utc=True))
        if labels.has_duplicates or not labels.is_monotonic_increasing:
            raise ValueError("Expected sorted, unique UTC hourly forecast timestamps")
        if not (labels == labels.floor("h")).all():
            raise ValueError("Forecast timestamps must align to hourly boundaries")
        frame["time"] = labels.tz_convert("Europe/Warsaw").astype(str)

        values = frame[WEATHER_CSV_COLUMNS[1:]].to_numpy(dtype=float)
        if not np.isfinite(values).all():
            raise ValueError("Forecast contains missing or nonfinite weather values")
        for name in ("cloud_cover_pct", "relative_humidity_2m_pct"):
            if not frame[name].between(0, 100).all():
                raise ValueError(f"Invalid {name} in weather forecast")
        for name in ("wind_speed_10m_kmh", "snowfall_cm", "shortwave_radiation_wm2"):
            if (frame[name] < 0).any():
                raise ValueError(f"Negative {name} in weather forecast")

        frame["issue_time_utc"] = issue_time_utc
        return frame

    def fetch(self) -> pd.DataFrame:
        """Request an hourly forecast in project-compatible units and column names."""
        params = {
            "latitude": SILESIA_LATITUDE,
            "longitude": SILESIA_LONGITUDE,
            "hourly": ",".join(OPEN_METEO_VARIABLES),
            "forecast_days": self.forecast_days,
            "timezone": "UTC",
            "wind_speed_unit": "kmh",
            "snowfall_unit": "cm",
        }
        request = Request(
            f"{OPEN_METEO_URL}?{urlencode(params)}",
            headers={"Accept": "application/json", "User-Agent": "HackoWatt/1.0"},
        )
        with urlopen(request, timeout=30) as response:
            payload = json.load(response)
        issue_time_utc = datetime.now(timezone.utc).isoformat()
        return self.parse_response(payload, issue_time_utc)

    def save_csv(self, destination: Path) -> Path:
        """Fetch and save the forecast CSV, creating its parent directory if needed."""
        destination = Path(destination)
        frame = self.fetch()
        destination.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(destination, index=False)
        return destination
