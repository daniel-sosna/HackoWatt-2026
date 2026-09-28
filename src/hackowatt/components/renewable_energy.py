"""Renewable Energy Simulator component and offline dashboard builder."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from .base import ProjectContext
from ..renewable import build_dashboard_data


def apply_model_profile(hourly: pd.DataFrame, profile_path: Path | None) -> pd.DataFrame:
    """Apply a colleague model through a small, explicit interchange contract."""
    if profile_path is None:
        hourly.attrs['load_source'] = 'historical total_kwh'
        return hourly
    profile = pd.read_csv(profile_path)
    required = {'timestamp_utc', 'load_kwh'}
    if not required.issubset(profile):
        raise ValueError(f'Model profile requires columns {sorted(required)}')
    source_time = pd.to_datetime(hourly.timestamp_utc, utc=True)
    model_time = pd.to_datetime(profile.timestamp_utc, utc=True)
    if model_time.duplicated().any() or len(profile) != len(hourly) or not model_time.equals(source_time):
        raise ValueError('Model profile timestamps must uniquely match hourly.csv in the current dashboard version')
    load = pd.to_numeric(profile.load_kwh, errors='raise')
    if not np.isfinite(load).all() or (load < 0).any():
        raise ValueError('Model load_kwh must be finite and nonnegative')
    result = hourly.copy()
    result['total_kwh'] = load.to_numpy(float)
    if 'occupancy_people' in profile:
        occupancy = pd.to_numeric(profile.occupancy_people, errors='raise')
        if (not np.isfinite(occupancy).all() or (occupancy < 0).any() or
                (occupancy > 4).any()):
            raise ValueError('occupancy_people must stay between 0 and 4')
        result['occupancy_mean'] = occupancy.to_numpy(float)
    model_id = (str(profile.model_id.iloc[0]) if 'model_id' in profile and
                profile.model_id.nunique(dropna=False) == 1 else profile_path.name)
    result.attrs['load_source'] = f'model profile: {model_id}'
    return result


def build_renewable_dashboard(input_folder: Path, output_folder: Path,
                              model_profile_path: Path | None = None) -> Path:
    input_folder, output_folder = Path(input_folder), Path(output_folder)
    hourly_path = input_folder / 'hourly.csv'
    events_path = input_folder / 'appliance_events.csv'
    if not hourly_path.exists() or not events_path.exists():
        raise FileNotFoundError(
            f'Expected {hourly_path} and {events_path}; run `python main.py generate` first.')
    hourly = pd.read_csv(hourly_path, dtype={'vacation_block': 'string'}, low_memory=False)
    hourly = apply_model_profile(hourly, model_profile_path)
    events = pd.read_csv(events_path)
    data = build_dashboard_data(hourly, events)
    template = (Path(__file__).resolve().parents[1] / 'renewable_dashboard.html').read_text(
        encoding='utf-8')
    output_folder.mkdir(parents=True, exist_ok=True)
    target = output_folder / 'renewable_energy_simulator.html'
    target.write_text(template.replace(
        '/* EMBED_DATA */',
        'const D=' + json.dumps(data, separators=(',', ':'), ensure_ascii=False) + ';'),
        encoding='utf-8')
    return target


class RenewableEnergyComponent:
    name = 'renewable-dashboard'
    help = 'Build the interactive Renewable Energy Simulator dashboard.'

    def add_arguments(self, subparsers: argparse._SubParsersAction) -> None:
        parser = subparsers.add_parser(self.name, help=self.help, description=self.help)
        parser.add_argument('--input', default='results/default',
                            help='Generated household directory relative to the project root.')
        parser.add_argument('--output', default='results/renewable',
                            help='Dashboard output directory relative to the project root.')
        parser.add_argument('--model-profile',
                            help=('Optional CSV relative to the project root with unique '
                                  'timestamp_utc and load_kwh; occupancy_people is optional.'))
        parser.set_defaults(component=self)

    def run(self, args, context: ProjectContext) -> int:
        target = build_renewable_dashboard(
            context.path(args.input), context.path(args.output),
            context.path(args.model_profile) if args.model_profile else None)
        print(target)
        return 0
