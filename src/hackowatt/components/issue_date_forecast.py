"""Command-line adapter for the portable issue-date forecast API."""
from __future__ import annotations

import argparse

from ..config import ProjectPaths
from ..issue_date_forecast import (
    ForecastRequest,
    forecast_from_issue_date,
    write_issue_date_forecast,
)


class ForecastComponent:
    name = 'forecast'
    help = 'Train through a supplied issue date and return one selected forecast horizon.'

    def add_arguments(self, subparsers: argparse._SubParsersAction) -> None:
        parser = subparsers.add_parser(self.name, help=self.help, description=self.help)
        parser.add_argument('--input', default='results/default/hourly.csv',
                            help='Hourly CSV relative to the project root.')
        parser.add_argument('--forecast-start-local', required=True,
                            help='First forecast hour in Europe/Warsaw time, for example "2025-09-10 00:00:00".')
        parser.add_argument('--horizon-hours', type=int, choices=(24, 72, 168), default=24,
                            help='Exact forecast horizon. The selected model depends on this value.')
        parser.add_argument('--forecast-weather',
                            help='Issued forecast-weather CSV relative to the project root. Future model weather uses this file.')
        parser.add_argument('--output', default='results/issue_date_forecast',
                            help='Output directory relative to the project root.')
        parser.set_defaults(component=self)

    def run(self, args: argparse.Namespace, paths: ProjectPaths) -> int:
        request = ForecastRequest(
            hourly_path=paths.resolve(args.input),
            forecast_start_local=args.forecast_start_local,
            horizon_hours=args.horizon_hours,
            forecast_weather_path=paths.resolve(args.forecast_weather) if args.forecast_weather else None,
        )
        result = forecast_from_issue_date(request)
        output_dir = paths.resolve(args.output)
        write_issue_date_forecast(result, output_dir)
        print(f"Model: {result.model_id}")
        print(f"Forecast: {result.manifest['forecast_start_local']} for {args.horizon_hours} hours")
        print(f"Saved forecast.csv, backtest_actual.csv, and manifest.json to {output_dir}")
        return 0
