"""Repository for the static CSV outputs produced by the simulator."""
from __future__ import annotations

import json
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


def load_historical_dashboard_source(directory: Path) -> dict:
    """Load the additional generated artifacts required by the historical UI."""
    household = load_generated_household(directory)
    directory = household.directory
    required = {
        "people": directory / "residents_hourly.csv",
        "comparison": directory / "eurostat_comparison.csv",
        "report": directory / "validation.json",
    }
    if any(not path.exists() for path in required.values()):
        raise FileNotFoundError("Historical dashboard data is incomplete; rerun `python main.py generate`.")
    return {
        "hourly": household.hourly,
        "people": pd.read_csv(required["people"]),
        "comparison": pd.read_csv(required["comparison"]),
        "report": json.loads(required["report"].read_text(encoding="utf-8")),
    }


def load_thermal_dashboard_source(directory: Path) -> dict:
    """Load generated thermal assumptions for the presentation-only planner."""
    directory = Path(directory)
    house_path, config_path = directory / "resolved_house.json", directory / "run_config.json"
    if not house_path.exists() or not config_path.exists():
        return {"available": False, "status": "House/config files unavailable"}
    return {
        "available": True,
        "house": json.loads(house_path.read_text(encoding="utf-8")),
        "settings": json.loads(config_path.read_text(encoding="utf-8")).get("thermal", {}),
        "status": "stateful one-zone RC building and well-mixed tank",
    }
