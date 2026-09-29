"""Validated static forecast-result CSV repository."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from ..domain import ForecastArtifacts


def load_forecast_artifacts(directory: Path) -> ForecastArtifacts:
    directory = Path(directory)
    paths = {
        "predictions": directory / "forecast_predictions.csv",
        "metrics": directory / "forecast_metrics.csv",
        "specification": directory / "forecast_model_spec.json",
    }
    missing = [str(path) for path in paths.values() if not path.exists()]
    if missing:
        raise FileNotFoundError("Forecast results are incomplete; run `python main.py forecast` first.")
    predictions = pd.read_csv(paths["predictions"])
    required = {"origin_utc", "timestamp_utc", "horizon_h", "model_id", "actual_kwh", "load_hat"}
    if not required.issubset(predictions):
        raise ValueError(f"forecast predictions require columns {sorted(required)}")
    metrics = pd.read_csv(paths["metrics"])
    return ForecastArtifacts(directory, predictions, metrics,
                             json.loads(paths["specification"].read_text(encoding="utf-8")))
