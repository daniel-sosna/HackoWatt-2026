"""Repository for the static CSV outputs produced by the simulator."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from ..domain import GeneratedHouseholdData


def read_hourly(path: Path) -> pd.DataFrame:
    """Read and validate the canonical generated hourly time series."""
    frame = pd.read_csv(path, dtype={"vacation_block": "string"}, low_memory=False)
    required = {"timestamp_utc", "total_kwh"}
    if not required.issubset(frame):
        raise ValueError(f"hourly data requires columns {sorted(required)}")
    timestamp = pd.to_datetime(frame["timestamp_utc"], utc=True, errors="raise")
    if timestamp.duplicated().any() or not timestamp.is_monotonic_increasing:
        raise ValueError("hourly.csv must have sorted unique UTC timestamps")
    if not (timestamp.diff().dropna() == pd.Timedelta(hours=1)).all():
        raise ValueError("hourly.csv must be continuous at hourly UTC frequency")
    frame.index = timestamp
    return frame


def load_generated_household(directory: Path) -> GeneratedHouseholdData:
    """Load the one generated household dataset used by all downstream features."""
    directory = Path(directory)
    hourly_path = directory / "hourly.csv"
    events_path = directory / "appliance_events.csv"
    if not hourly_path.exists() or not events_path.exists():
        raise FileNotFoundError(
            f"Expected {hourly_path} and {events_path}; run `python main.py generate` first."
        )
    return GeneratedHouseholdData(directory, read_hourly(hourly_path), pd.read_csv(events_path))
