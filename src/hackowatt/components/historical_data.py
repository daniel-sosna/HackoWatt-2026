"""CLI adapter for historical-profile generation."""
from __future__ import annotations

import argparse

from .base import ProjectContext
from ..services import generate_historical


class HistoricalDataComponent:
    name = "generate"
    help = "Generate synthetic historical household data."

    def add_arguments(self, subparsers: argparse._SubParsersAction) -> None:
        parser = subparsers.add_parser(self.name, help=self.help, description=self.help)
        parser.add_argument("--config", default="config/default.json", help="Configuration JSON relative to the project root.")
        parser.add_argument("--output", help="Optional output directory, relative to the project root.")
        parser.set_defaults(component=self)

    def run(self, args: argparse.Namespace, context: ProjectContext) -> int:
        output = context.path(args.output) if args.output else None
        generate_historical(context.root, context.path(args.config), output)
        return 0
