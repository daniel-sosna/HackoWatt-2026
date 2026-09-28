"""Adapter that exposes the existing offline forecast renderer as a component."""
from __future__ import annotations

import argparse
import importlib.util

from .base import ProjectContext


class ForecastDashboardComponent:
    name = 'forecast-dashboard'
    help = 'Build the offline comparison dashboard for forecast results.'

    def add_arguments(self, subparsers: argparse._SubParsersAction) -> None:
        parser = subparsers.add_parser(self.name, help=self.help, description=self.help)
        parser.add_argument('--input', default='results/forecast', help='Forecast result directory relative to the project root.')
        parser.set_defaults(component=self)

    def run(self, args: argparse.Namespace, context: ProjectContext) -> int:
        # The self-contained HTML renderer remains a standalone module for now.
        # Loading it through this adapter gives the main application a stable
        # command while keeping the renderer usable by itself in PyCharm.
        source = context.root / 'visualize_forecasts.py'
        spec = importlib.util.spec_from_file_location('hackowatt_legacy_forecast_dashboard', source)
        if spec is None or spec.loader is None:
            raise RuntimeError(f'Cannot load forecast dashboard renderer: {source}')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.build(context.path(args.input))
        return 0
