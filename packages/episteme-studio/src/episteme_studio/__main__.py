"""Command-line interface entry point for Episteme Studio."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import uvicorn

from episteme_studio.app import create_app
from episteme_studio.security import SecurityConfigurationError, validate_host_and_token
from episteme_studio.settings import StudioSettings


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser for episteme-studio.

    Returns
    -------
    argparse.ArgumentParser
        Configured CLI parser.
    """
    parser = argparse.ArgumentParser(
        prog="episteme-studio",
        description="Episteme Studio — workbench for Episteme runs and artifacts.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    serve_parser = subparsers.add_parser(
        "serve", help="Start the Episteme Studio web server."
    )
    serve_parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Host interface to bind (default: 127.0.0.1).",
    )
    serve_parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to listen on (default: 8000).",
    )
    serve_parser.add_argument(
        "--env-file",
        type=str,
        default=None,
        help="Optional path to an environment file to load.",
    )
    serve_parser.add_argument(
        "--profile",
        type=str,
        default=None,
        help="Pipeline profile name or config JSON path to preload.",
    )
    serve_parser.add_argument(
        "--demo",
        action="store_true",
        help="Launch with canned demonstration runs and mock dependencies.",
    )
    serve_parser.add_argument(
        "--read-only",
        action="store_true",
        help="Launch in read-only mode (disables execution triggers and filesystem mutations).",
    )
    serve_parser.add_argument(
        "--token",
        type=str,
        default=None,
        help="Authentication token (required when binding to non-loopback hosts).",
    )
    serve_parser.add_argument(
        "--runs-dir",
        type=str,
        default=None,
        help="Root path to directory containing pipeline run manifests (default: auto-detected .pipeline_runs).",
    )
    serve_parser.add_argument(
        "--artifacts-dir",
        type=str,
        default=None,
        help="Root path to directory containing artifact envelopes (default: auto-detected .pipeline_artifacts).",
    )

    serve_parser.add_argument(
        "--dev",
        nargs="?",
        const="http://127.0.0.1:5173",
        default=None,
        help="Run Vite in dev mode or specify Vite dev server URL (default: http://127.0.0.1:5173).",
    )

    return parser


def main(argv: list[str] | None = None) -> None:
    """Run the CLI application.

    Parameters
    ----------
    argv : list of str or None, optional
        Command line arguments. If None, sys.argv[1:] is used.
    """
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "serve":
        kwargs: dict[str, Any] = {
            "host": args.host,
            "port": args.port,
            "token": args.token,
            "demo_mode": args.demo,
            "read_only": args.read_only,
            "dev_mode": args.dev,
        }
        if args.runs_dir is not None:
            kwargs["runs_dir"] = Path(args.runs_dir)
        if args.artifacts_dir is not None:
            kwargs["artifacts_dir"] = Path(args.artifacts_dir)

        settings = StudioSettings(**kwargs)
        try:
            validate_host_and_token(settings)
        except SecurityConfigurationError as err:
            sys.stderr.write(f"Security Error: {err}\n")
            sys.exit(1)

        app = create_app(settings)
        uvicorn.run(app, host=settings.host, port=settings.port, log_level="info")


if __name__ == "__main__":
    main()
