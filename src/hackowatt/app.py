"""Canonical application entry point and component dispatcher."""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from .components import built_in_registry
from .components.base import ProjectContext


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog='hackowatt', description='HackoWatt household-data application.')
    parser.add_argument('--project-root', type=Path,
                        help='Project root; use when running the installed command outside the repository.')
    subparsers = parser.add_subparsers(dest='command', required=True, title='components')
    built_in_registry().add_subparsers(subparsers)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.component.run(args, ProjectContext.discover(args.project_root))
