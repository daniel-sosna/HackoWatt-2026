"""CLI adapter for downloading future Silesia weather."""
from __future__ import annotations

import argparse

from ..config import ProjectPaths
from ..services import fetch_weather_forecast


class WeatherForecastComponent:
    name = "fetch-weather"
    help = "Download hourly Open-Meteo weather forecasts for Silesia."

    def add_arguments(self, subparsers: argparse._SubParsersAction) -> None:
        parser = subparsers.add_parser(self.name, help=self.help, description=self.help)
        parser.add_argument(
            "--output", default="results/weather_forecast.csv",
            help="Destination CSV relative to the project root.",
        )
        parser.add_argument(
            "--days", type=int, default=7,
            help="Forecast length in days (Open-Meteo supports 1 to 16).",
        )
        parser.set_defaults(component=self)

    def run(self, args: argparse.Namespace, paths: ProjectPaths) -> int:
        destination = fetch_weather_forecast(paths.resolve(args.output), args.days)
        print(f"Saved Silesia weather forecast to {destination}")
        return 0
