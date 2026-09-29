"""CLI adapter for the unified Streamlit presentation layer."""
from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
import subprocess
import sys

from ..config import ProjectPaths


class DashboardComponent:
    name = "dashboard"
    help = "Launch the unified Streamlit dashboard."

    def add_arguments(self, subparsers: argparse._SubParsersAction) -> None:
        parser = subparsers.add_parser(self.name, help=self.help, description=self.help)
        parser.add_argument("--input", default="results/default", help="Generated household directory.")
        parser.add_argument("--forecast-input", default="results/forecast", help="Forecast result directory.")
        parser.add_argument("--port", type=int, help="Optional local Streamlit port.")
        parser.set_defaults(component=self)

    def run(self, args: argparse.Namespace, paths: ProjectPaths) -> int:
        if importlib.util.find_spec("streamlit") is None:
            raise RuntimeError("Streamlit is not installed. Run `python -m pip install -r requirements.txt`.")
        command = [sys.executable, "-m", "streamlit", "run", str(paths.root / "app" / "streamlit_app.py")]
        if args.port:
            command.extend(["--server.port", str(args.port)])
        command.extend(["--", "--project-root", str(paths.root), "--input", args.input,
                        "--forecast-input", args.forecast_input])
        return subprocess.call(command, cwd=paths.root)
