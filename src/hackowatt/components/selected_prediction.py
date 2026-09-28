"""Component that publishes the user's approved forecast-model combination."""
from __future__ import annotations

import argparse

from .base import ProjectContext
from ..ml_benchmark import create_selected_prediction_package


class SelectedPredictionComponent:
    name = 'selected-prediction'
    help = 'Create input/output forecast package using the approved model by horizon.'

    def add_arguments(self, subparsers: argparse._SubParsersAction) -> None:
        parser = subparsers.add_parser(self.name, help=self.help, description=self.help)
        parser.add_argument('--input', default='results/default/hourly.csv', help='Hourly CSV relative to the project root.')
        parser.add_argument('--output', default='results/prediction', help='Small input/output package directory.')
        parser.add_argument('--forecast-start-local', default='2025-09-10 00:00:00',
                            help='First forecast hour in Europe/Warsaw time.')
        parser.set_defaults(component=self)

    def run(self, args: argparse.Namespace, context: ProjectContext) -> int:
        metrics = create_selected_prediction_package(
            context.path(args.input), context.path(args.output), args.forecast_start_local)
        print(metrics[['model_id', 'horizon_hours', 'mae', 'rmse', 'wape_pct', 'bias_kwh']].round(3).to_string(index=False))
        print(f'Saved selected prediction input/output package to {context.path(args.output)}')
        return 0
