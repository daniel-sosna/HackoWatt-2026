"""CLI adapter for historical-profile generation."""
from __future__ import annotations

import argparse

from ..config import ProjectPaths
from ..services import generate_historical


class HistoricalDataComponent:
    name = "generate"
    help = "Generate synthetic historical household data."

    def add_arguments(self, subparsers: argparse._SubParsersAction) -> None:
        parser = subparsers.add_parser(self.name, help=self.help, description=self.help)
        parser.add_argument("--config", default="config/default.json", help="Configuration JSON relative to the project root.")
        parser.add_argument("--output", help="Optional output directory, relative to the project root.")
        parser.set_defaults(component=self)

    def run(self, args: argparse.Namespace, paths: ProjectPaths) -> int:
        output = paths.resolve(args.output) if args.output else None
        generate_historical(paths.root, paths.resolve(args.config), output)
        return 0
