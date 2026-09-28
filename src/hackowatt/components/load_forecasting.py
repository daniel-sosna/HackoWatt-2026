"""Forecast-model component built on generated historical data."""
from __future__ import annotations

import argparse

from .base import ProjectContext
from ..forecasting import run_forecast_experiment


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

    def run(self, args: argparse.Namespace, context: ProjectContext) -> int:
        _, metrics, spec = run_forecast_experiment(
            context.path(args.input), context.path(args.output), args.test_days, args.origin_stride_hours)
        print(metrics[['model_id', 'bucket', 'mae_kwh', 'rmse_kwh', 'wape_pct', 'total_error_pct',
                       'peak_hour_mae_kwh', 'peak_timing_mae_h']].round(3).to_string(index=False))
        print(f"Saved {spec['origins']} rolling origins to {context.path(args.output)}")
        return 0
