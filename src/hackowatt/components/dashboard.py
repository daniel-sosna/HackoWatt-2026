"""CLI adapter for the local native-dashboard web server."""
from __future__ import annotations

import argparse
from ..config import ProjectPaths
from ..web import create_web_app


class DashboardComponent:
    name = "dashboard"
    help = "Launch the unified local web dashboard."

    def add_arguments(self, subparsers: argparse._SubParsersAction) -> None:
        parser = subparsers.add_parser(self.name, help=self.help, description=self.help)
        parser.add_argument("--input", default="results/default", help="Generated household directory.")
        parser.add_argument("--port", type=int, default=8501, help="Local server port (default: 8501).")
        parser.set_defaults(component=self)

    def run(self, args: argparse.Namespace, paths: ProjectPaths) -> int:
        try:
            import uvicorn
        except ImportError as error:
            raise RuntimeError("Web dependencies are not installed. Run `python -m pip install -r requirements.txt`.") from error
        app = create_web_app(paths.resolve(args.input))
        print(f"HackoWatt dashboard: http://127.0.0.1:{args.port}")
        uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="info")
        return 0
