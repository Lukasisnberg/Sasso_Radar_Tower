#!/usr/bin/env python3
"""CLI test tool — fetches live aircraft from adsb.fi and prints a table.

Usage:
    python -m flugradar.cli                        # use defaults / env vars
    python -m flugradar.cli --lat 47.38 --lon 8.54 --radius 80
    python -m flugradar.cli --unit nm --min-alt 5000
    python -m flugradar.cli --watch                # continuous refresh
"""

import argparse
import os
import sys
import time

from flugradar.config.settings import AppSettings
from flugradar.data_sources.adsb_fi import AdsbFiClient
from flugradar.data_sources.geo import km_to_unit, unit_label
from flugradar.data_sources.models import Aircraft


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Sasso Radar Tower — ADS-B CLI")
    p.add_argument("--lat", type=float, help="Home latitude")
    p.add_argument("--lon", type=float, help="Home longitude")
    p.add_argument("--radius", type=float, help="Scan radius in km")
    p.add_argument("--unit", choices=("km", "sm", "nm"), help="Distance unit")
    p.add_argument("--min-alt", type=int, default=None, help="Minimum altitude filter (ft)")
    p.add_argument("--watch", action="store_true", help="Continuous refresh mode")
    p.add_argument("--interval", type=float, default=None, help="Refresh interval in seconds")
    return p


def _print_table(aircraft: list[Aircraft], unit: str, min_alt: int) -> None:
    filtered = [
        ac for ac in aircraft
        if (ac.altitude_ft or 0) >= min_alt and not ac.is_on_ground
    ]

    ulbl = unit_label(unit)
    hdr = (
        f"{'Callsign':<10} {'ICAO':<8} {'Type':<5} "
        f"{'Alt ft':>8} {'Spd kt':>7} {'Hdg':>5} "
        f"{'Dist':>7} {'Brg':>5} {'Sqwk':<5} {'Flags'}"
    )
    sep = "-" * len(hdr)

    print(f"\n  Aircraft in range: {len(filtered)} (of {len(aircraft)} total)")
    print(f"  {sep}")
    print(f"  {hdr}")
    print(f"  {sep}")

    for ac in filtered:
        dist_val = km_to_unit(ac.distance_km, unit) if ac.distance_km else 0
        flags = []
        if ac.is_emergency:
            flags.append(f"EMG:{ac.squawk}")
        if ac.category and ac.category.startswith("A"):
            cat_num = ac.category[1:] if len(ac.category) > 1 else ""
            if cat_num in ("5", "6", "7"):
                flags.append("MIL?")

        print(
            f"  {ac.display_label:<10} {ac.icao_hex:<8} {(ac.aircraft_type or '-'):<5} "
            f"{(ac.altitude_ft or 0):>8} {(ac.ground_speed_kt or 0):>7.0f} "
            f"{(ac.track_deg or 0):>5.0f} "
            f"{dist_val:>6.1f}{ulbl} {(ac.bearing_deg or 0):>4.0f}° "
            f"{(ac.squawk or '-'):<5} {' '.join(flags)}"
        )

    print(f"  {sep}\n")


def main() -> None:
    args = _build_parser().parse_args()
    settings = AppSettings()

    if args.lat is not None:
        settings.home.lat = args.lat
    if args.lon is not None:
        settings.home.lon = args.lon
    if args.radius is not None:
        settings.home.radius_km = args.radius
    if args.unit:
        settings.distance_unit = args.unit
    if args.interval is not None:
        settings.adsb.poll_interval_s = args.interval

    min_alt = args.min_alt if args.min_alt is not None else settings.min_altitude_ft

    client = AdsbFiClient(settings.adsb, settings.home)

    print(
        f"Sasso Radar Tower v0.1 — scanning {settings.home.radius_km:.0f} km "
        f"around ({settings.home.lat:.4f}, {settings.home.lon:.4f})"
    )

    try:
        if args.watch:
            while True:
                aircraft = client.get_aircraft(force_refresh=True)
                os.system("clear" if os.name == "posix" else "cls")
                print(
                    f"Sasso Radar Tower v0.1 — scanning {settings.home.radius_km:.0f} km "
                    f"around ({settings.home.lat:.4f}, {settings.home.lon:.4f})  "
                    f"[refresh every {settings.adsb.poll_interval_s:.0f}s — Ctrl+C to stop]"
                )
                _print_table(aircraft, settings.distance_unit, min_alt)
                time.sleep(settings.adsb.poll_interval_s)
        else:
            aircraft = client.get_aircraft(force_refresh=True)
            _print_table(aircraft, settings.distance_unit, min_alt)
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        client.close()


if __name__ == "__main__":
    main()
