"""Model-training benchmark component for prepared household data."""
from __future__ import annotations

import argparse

from .base import ProjectContext
from ..ml_benchmark import run_model_benchmark


class ModelBenchmarkComponent:
    name = 'model-benchmark'
    help = 'Prepare separate ML data, forecast occupancy, and compare direct and modular models.'

    def add_arguments(self, subparsers: argparse._SubParsersAction) -> None:
        parser = subparsers.add_parser(self.name, help=self.help, description=self.help)
        parser.add_argument('--input', default='results/default/hourly.csv', help='Hourly CSV relative to the project root.')
        parser.add_argument('--output', default='results/model_benchmark', help='Output directory relative to the project root.')
        parser.add_argument('--test-days', type=int, default=90, help='Chronological hold-out duration in days.')
        parser.set_defaults(component=self)

    def run(self, args: argparse.Namespace, context: ProjectContext) -> int:
        occupancy, load, spec = run_model_benchmark(
            context.path(args.input), context.path(args.output), args.test_days)
        print('Occupancy forecast metrics:')
        print(occupancy[['model_id', 'mae', 'rmse', 'wape_pct']].round(3).to_string(index=False))
        print('\nLoad forecast metrics:')
        print(load[['model_id', 'mae', 'rmse', 'wape_pct', 'bias_kwh']].round(3).to_string(index=False))
        print(f"Saved prepared train/test data, models, predictions, charts, and dashboard to {context.path(args.output)}")
        print(f"Test period: {spec['test_start_utc']} to {spec['test_end_utc']}")
        return 0
