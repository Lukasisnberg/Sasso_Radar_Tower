# Sasso Radar Tower

Live ADS-B flight radar for Raspberry Pi 4 with a round 4" touch display
(Waveshare 4inch DSI LCD (C), 720x720). Fully self-built pygame display app
plus a Flask web portal for remote configuration — see
[docs/ANFORDERUNGEN.md](docs/ANFORDERUNGEN.md) for the full spec and
[CLAUDE.md](CLAUDE.md) for current build status.

## Quick start (development, no display needed)

```bash
# Install in development mode
pip install -e ".[dev]"

# Run the CLI test tool (live aircraft around Zurich)
python -m flugradar.cli

# Custom location and radius
python -m flugradar.cli --lat 48.8566 --lon 2.3522 --radius 80

# Continuous watch mode
python -m flugradar.cli --watch --interval 5

# Nautical miles, minimum altitude filter
python -m flugradar.cli --unit nm --min-alt 5000
```

To run the actual pygame display or the web portal locally:

```bash
pip install -e ".[display,web]"

python -m flugradar.main --demo        # display app, simulated aircraft, no network
python -m flugradar.web.run            # web portal on http://localhost:5000
```

## Configuration

Copy `.env.example` to `.env` and adjust values — it documents every
supported environment variable. Priority order: **environment variables
> portal settings (saved via the web UI) > built-in defaults**.

Runtime settings changed through the web portal are stored in
`~/.local/share/flugradar/settings.json` (or `$FLUGRADAR_DATA_DIR` if set)
and picked up by the running display app within ~2 seconds, no restart
needed — except for API keys, which take effect on the next start.

## Web portal

```bash
python -m flugradar.web.run --port 5000
```

Open `http://<hostname>.local:5000` (or the Pi's IP) from any device on
the same network. Pages: **Radar** (location/zoom/units), **Display**
(theme, aircraft icon set, map overlay, idle behaviour), **API Keys**
(FR24/Tomorrow.io/AirLabs/adsbdb/openAIP), **System** (reboot/shutdown).
No internet access is required to reach it — it only serves the local
network.

## Raspberry Pi deployment

```bash
sudo bash install.sh
```

Installs system dependencies, creates a Python virtualenv, copies the
project to `~/sasso-radar-tower`, and registers two systemd services
(`system/systemd/flugradar-display.service`,
`flugradar-web.service`) that start on boot. Two display backends,
switchable via `DISPLAY_BACKEND` in `.env`:

- `desktop` — runs over the existing X11/Xwayland desktop session
  (default; compatible with screen-sharing tools like Pi Connect while
  developing)
- `kiosk` — direct KMS/DRM access to the physical panel, no desktop
  session required (for the finished, permanently-mounted display)

To deploy a code update to an existing install, re-sync the project
directory (e.g. `rsync -a --exclude='.git' --exclude='.venv' ./
~/sasso-radar-tower/`) and restart both services.

## Tests

```bash
python -m pytest -v
```

## Project structure

```
flugradar/
  config/            # Env handling, portal settings file, priority logic
  data_sources/       # adsb.fi, adsbdb, AirLabs, Tomorrow.io, aircraft
                       # photos, airline branding, airport name lookup
  maps/                # Tile download/cache, base map + overlay compositing
                         # (CARTO/OSM base, openAIP/RainViewer overlays)
  display/              # pygame app, screens/, gestures, theme, icon set
  web/                   # Flask portal: routes, templates, static
  system/                 # systemd unit templates, boot splash
  tests/                   # Unit tests (mocked network, no live calls)
  cli.py                    # CLI test tool (no display needed)
  main.py                    # Display app entry point (flugradar-display)
  web/run.py                  # Web portal entry point (flugradar-web)
install.sh                     # Raspberry Pi installer (sudo bash install.sh)
docs/ANFORDERUNGEN.md           # Full project specification
```

## Data sources & attribution

- **[adsb.fi](https://adsb.fi/)** — live ADS-B aircraft positions
  (free open-data API, no key required)
- **[adsbdb.com](https://www.adsbdb.com/)** — free aircraft/route/airline
  enrichment, no key required (default enrichment source; AirLabs is used
  instead if a key is configured). Flight route data is the work of David
  Taylor, Edinburgh and Jim Mason, Glasgow, and may not be copied,
  published, or incorporated into other databases without their explicit
  permission — route data is therefore cached only in RAM, never on disk.
- **CARTO / OpenStreetMap** — map tile backgrounds
  (© CARTO, © OpenStreetMap contributors)
- **[ADS-B Radar for macOS](https://adsb-radar.com/)** — aircraft type
  SVG icons used by the "detailed" icon set
  (free for personal/commercial use, backlink required — see
  `flugradar/assets/icons/aircraft/LICENSE.txt`)
- **[openAIP](https://www.openaip.net/)** — optional aviation overlay
  (airspaces/airports/navaids) on top of the map background, requires a
  free account and API key. Data licensed
  [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/)
  (attribution required, **non-commercial use only**)
- **[planespotters.net](https://www.planespotters.net/)** — aircraft
  photos in the detail view, with photographer attribution when available
- **[RainViewer](https://www.rainviewer.com/)** — optional rain radar
  overlay on top of the map background, no key required. Free for
  personal/educational use only

## License

This project's own code is MIT-licensed — see [LICENSE](LICENSE).

That covers the code only. Third-party data and assets pulled in at
runtime (openAIP's CC BY-NC 4.0 aviation data, adsbdb's route-data
restrictions, the adsb-radar.com icon set's backlink requirement) keep
their own licenses regardless of how this repository is licensed — see
the attribution list above and `flugradar/assets/icons/aircraft/LICENSE.txt`.
