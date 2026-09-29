"""Small shared value objects passed between application layers."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd


@dataclass(frozen=True)
class GeneratedHouseholdData:
    """Validated generated files for one simulation run."""

    directory: Path
    hourly: pd.DataFrame
    appliance_events: pd.DataFrame
