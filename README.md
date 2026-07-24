# Sasso Radar Tower

Live ADS-B flight radar for Raspberry Pi 4 with a round 4" touch display
(Waveshare 4inch DSI LCD (C), 720x720).

## Quick start

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

## Configuration

Copy `.env.example` to `.env` and adjust values. Environment variables
override defaults; portal settings (saved via the web UI) override both.

## Tests

```bash
python -m pytest -v
```

## Project structure

```
flugradar/
  config/            # Environment handling, settings file, priority logic
  data_sources/      # adsb.fi, FR24, AirLabs, Tomorrow.io, RainViewer clients
  maps/              # Tile download, cache, colour post-processing
  display/           # pygame app: screens/, gestures, theme
  web/               # Flask portal: routes, templates, static
  system/            # systemd unit template, install script, boot splash
  tests/             # Unit tests
  cli.py             # CLI test tool
  main.py            # Display app entry point (future)
```

## Data sources & attribution

- **[adsb.fi](https://adsb.fi/)** — live ADS-B aircraft positions
  (free open-data API, no key required)
- **CARTO / OpenStreetMap** — map tile backgrounds
  (© CARTO, © OpenStreetMap contributors)
- **[ADS-B Radar for macOS](https://adsb-radar.com/)** — aircraft type
  SVG icons used by the "detailed" icon set
  (free for personal/commercial use, backlink required — see
  `flugradar/assets/icons/aircraft/LICENSE.txt`)

## License

MIT
