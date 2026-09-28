"""Renewable Energy Simulator component and offline dashboard builder."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from .base import ProjectContext
from ..renewable import build_dashboard_data


def build_renewable_dashboard(input_folder: Path, output_folder: Path) -> Path:
    input_folder, output_folder = Path(input_folder), Path(output_folder)
    hourly_path = input_folder / 'hourly.csv'
    events_path = input_folder / 'appliance_events.csv'
    if not hourly_path.exists() or not events_path.exists():
        raise FileNotFoundError(
            f'Expected {hourly_path} and {events_path}; run `python main.py generate` first.')
    hourly = pd.read_csv(hourly_path, dtype={'vacation_block': 'string'}, low_memory=False)
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
        parser.set_defaults(component=self)

    def run(self, args, context: ProjectContext) -> int:
        target = build_renewable_dashboard(
            context.path(args.input), context.path(args.output))
        print(target)
        return 0
