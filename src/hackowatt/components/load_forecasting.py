"""Forecast-model component built on generated historical data."""
from __future__ import annotations

import argparse

from ..config import ProjectPaths
from ..services import run_forecast


class LoadForecastComponent:
    name = 'forecast'
    help = 'Train and compare the recursive 24-hour, 3-day and 7-day load forecasts.'

    def add_arguments(self, subparsers: argparse._SubParsersAction) -> None:
        parser = subparsers.add_parser(self.name, help=self.help, description=self.help)
        parser.add_argument('--input', default='results/default/hourly.csv', help='Hourly CSV relative to the project root.')
        parser.add_argument('--output', default='results/forecast', help='Output directory relative to the project root.')
        parser.add_argument('--test-days', type=int, default=90)
        parser.add_argument('--origin-stride-hours', type=int, default=168)
        parser.set_defaults(component=self)

    def run(self, args: argparse.Namespace, paths: ProjectPaths) -> int:
        artifacts = run_forecast(
            paths.resolve(args.input), paths.resolve(args.output), args.test_days, args.origin_stride_hours)
        metrics, spec = artifacts.metrics, artifacts.specification
        print(metrics[['model_id', 'bucket', 'mae_kwh', 'rmse_kwh', 'wape_pct', 'total_error_pct',
                       'peak_hour_mae_kwh', 'peak_timing_mae_h']].round(3).to_string(index=False))
        print(f"Saved {spec['origins']} rolling origins to {paths.resolve(args.output)}")
        return 0
