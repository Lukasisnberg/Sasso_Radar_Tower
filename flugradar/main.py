#!/usr/bin/env python3
"""Entry point for the pygame radar display application.

Usage:
    python -m flugradar.main
    python -m flugradar.main --demo
    python -m flugradar.main --demo --no-map --no-mask
    python -m flugradar.main --lat 48.85 --lon 2.35 --radius 80
"""

import argparse
import logging

from flugradar.config.settings import AppSettings
from flugradar.display.app import RadarApp


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Sasso Radar Tower — Display")
    p.add_argument("--lat", type=float, help="Home latitude")
    p.add_argument("--lon", type=float, help="Home longitude")
    p.add_argument("--radius", type=float, help="Scan radius in km")
    p.add_argument("--size", type=int, default=720, help="Window size in pixels")
    p.add_argument("--unit", choices=("km", "sm", "nm"), help="Distance unit")
    p.add_argument("--theme", choices=("dark", "amber"), default=None, help="Colour theme")
    p.add_argument("--demo", action="store_true", help="Use simulated aircraft (no network)")
    p.add_argument("--no-map", action="store_true", help="Disable map tile background")
    p.add_argument("--no-mask", action="store_true", help="Disable circular mask (square window)")
    p.add_argument("--rotation", type=float, default=0.0, help="Display rotation in degrees")
    p.add_argument("--debug", action="store_true", help="Enable debug logging")
    return p


def main() -> None:
    args = _build_parser().parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    settings = AppSettings()
    if args.lat is not None:
        settings.home.lat = args.lat
    if args.lon is not None:
        settings.home.lon = args.lon
    if args.radius is not None:
        settings.home.radius_km = args.radius
    if args.unit:
        settings.distance_unit = args.unit

    app = RadarApp(
        settings,
        screen_size=args.size,
        demo_mode=args.demo,
        enable_map=not args.no_map,
        round_mask=not args.no_mask,
        rotation_deg=args.rotation,
    )
    app.run()


if __name__ == "__main__":
    main()
