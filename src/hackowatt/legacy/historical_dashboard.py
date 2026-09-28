"""Archived offline diagnostic dashboard; use the unified Streamlit dashboard."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from ..components.base import ProjectContext
from ..simulation.behaviour import ACTIVITIES, PEOPLE
from ..services import generate_historical


def build_dashboard(folder: Path) -> Path:
    """Create an offline diagnostic dashboard for a generated data set."""
    folder = Path(folder)
    df = pd.read_csv(folder / 'hourly.csv', dtype={'vacation_block': 'string'}, low_memory=False)
    people = pd.read_csv(folder / 'residents_hourly.csv')
    report = json.loads((folder / 'validation.json').read_text(encoding='utf-8'))
    energy = [column for column in df if column.endswith('_kwh') and column not in
              ('total_kwh', 'hot_water_unmet_kwh', 'thermal_residual_kwh')]
    data = {
        'time': df.timestamp_local.tolist(), 'energy_names': energy, 'activities': ACTIVITIES, 'people': {},
        'energy': df[energy].round(5).to_numpy().tolist(), 'total': df.total_kwh.round(4).tolist(),
        'outdoor': df.temperature_2m.round(2).tolist(), 'indoor': df.indoor_c.round(2).tolist(),
        'tank': df.tank_c.round(2).tolist(), 'setpoint': df.setpoint_c.round(2).tolist(),
        'occupancy': df.occupancy_mean.round(3).tolist(),
        'family_vacation': df.family_vacation.astype(bool).tolist(),
        'night_ventilation': df.night_ventilation_active_fraction.round(3).tolist(),
        'comparison': pd.read_csv(folder / 'eurostat_comparison.csv').replace({np.nan: None}).to_dict('records'),
        'report': report,
    }
    for person in PEOPLE:
        person_data = people[people.person == person]
        data['people'][person] = {
            'minutes': person_data[[activity + '_minutes' for activity in ACTIVITIES]].to_numpy().tolist(),
            'home': person_data.home_minutes.tolist(),
        }
    template = (Path(__file__).resolve().parent / 'assets' / 'dashboard.html').read_text(encoding='utf-8')
    target = folder / 'dashboard.html'
    target.write_text(template.replace('/* EMBED_DATA */', 'const D=' + json.dumps(
        data, separators=(',', ':'), ensure_ascii=False) + ';'), encoding='utf-8')
    return target


class HistoricalDataComponent:
    name = 'generate'
    help = 'Generate synthetic historical household data.'

    def add_arguments(self, subparsers: argparse._SubParsersAction) -> None:
        parser = subparsers.add_parser(self.name, help=self.help, description=self.help)
        parser.add_argument('--config', default='config/default.json', help='Configuration JSON relative to the project root.')
        parser.add_argument('--output', help='Optional output directory, relative to the project root.')
        parser.set_defaults(component=self)

    def run(self, args: argparse.Namespace, context: ProjectContext) -> int:
        output = context.path(args.output) if args.output else None
        generate_historical(context.root, context.path(args.config), output)
        return 0


class HistoricalDashboardComponent:
    name = 'dashboard'
    help = 'Build the offline diagnostic dashboard for generated historical data.'

    def add_arguments(self, subparsers: argparse._SubParsersAction) -> None:
        parser = subparsers.add_parser(self.name, help=self.help, description=self.help)
        parser.add_argument('--input', default='results/default', help='Generated data directory relative to the project root.')
        parser.set_defaults(component=self)

    def run(self, args: argparse.Namespace, context: ProjectContext) -> int:
        print(build_dashboard(context.path(args.input)))
        return 0
