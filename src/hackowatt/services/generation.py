"""Application service coordinating static inputs, weather and simulation."""
from __future__ import annotations

from pathlib import Path

import numpy as np

from ..data import load_calendars, load_config, load_reference, resolve_house
from ..simulation.profile import generate_profile
from ..weather import CsvWeatherProvider, WeatherProvider


def generate_historical(root: Path, config_path: Path, output_override: Path | None = None,
                        weather_provider: WeatherProvider | None = None) -> Path:
    """Generate one household profile from validated static source files."""
    root, config_path = Path(root), Path(config_path)
    configuration = load_config(config_path)
    streams = [np.random.default_rng(seed) for seed in np.random.SeedSequence(configuration["seed"]).spawn(3)]
    house = resolve_house(configuration, streams[0])
    provider = weather_provider or CsvWeatherProvider(root / "data/raw/katowice_weather_2024_today.csv")
    weather, audit = provider.historical(configuration)
    weather.attrs["audit"] = audit
    public, school = load_calendars(root, configuration)
    reference = load_reference(root / "data/raw/activity_time_use_full.csv")
    output = Path(output_override) if output_override else root / configuration["output"]["directory"]
    return generate_profile(root, configuration, weather, public, school, reference, house,
                            streams[1], streams[2], output)
