"""Provider boundary for weather used by simulation and forecasting."""
from __future__ import annotations

from pathlib import Path
from typing import Protocol

import pandas as pd

from ..data import load_weather


class WeatherProvider(Protocol):
    """Returns validated canonical hourly weather and its source audit."""

    def historical(self, configuration: dict) -> tuple[pd.DataFrame, dict]: ...


class CsvWeatherProvider:
    """Current static-file provider; replace this class for a real provider later."""

    def __init__(self, csv_path: Path):
        self.csv_path = Path(csv_path)

    def historical(self, configuration: dict) -> tuple[pd.DataFrame, dict]:
        return load_weather(self.csv_path, configuration)
