#!/usr/bin/env python3
"""Entry point for the Flask web portal.

Usage:
    python -m flugradar.web.run
    python -m flugradar.web.run --port 8080
    python -m flugradar.web.run --host 0.0.0.0
"""

import argparse
import logging

from flugradar.config.settings import AppSettings
from flugradar.web.app import create_app


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Sasso Radar Tower — Web Portal")
    p.add_argument("--host", default="0.0.0.0", help="Bind address")
    p.add_argument("--port", type=int, default=5000, help="Port")
    p.add_argument("--debug", action="store_true", help="Enable debug mode")
    return p


def main() -> None:
    args = _build_parser().parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )
    settings = AppSettings()
    app = create_app(settings)
    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()
