"""Application service for the forecasting experiment."""
from __future__ import annotations

from pathlib import Path

from ..data import load_forecast_artifacts
from ..domain import ForecastArtifacts
from ..forecasting import run_forecast_experiment


def run_forecast(hourly_path: Path, output_directory: Path, test_days: int = 90,
                 origin_stride_hours: int = 168) -> ForecastArtifacts:
    """Run the canonical 24-hour, 3-day and 7-day backtest and load its artifacts."""
    run_forecast_experiment(Path(hourly_path), Path(output_directory), test_days, origin_stride_hours)
    return load_forecast_artifacts(Path(output_directory))
