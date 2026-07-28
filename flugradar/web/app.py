"""Flask web portal for remote configuration of Sasso Radar Tower."""

import json
import logging
import os

from flask import Flask, render_template, request, jsonify, redirect, url_for

from flugradar import __version__
from flugradar.config.locations import LOCATIONS
from flugradar.config.settings import AppSettings, PORTAL_SETTINGS_FILE
from flugradar.data_sources.weather import WeatherClient
from flugradar.system import network_watchdog
from flugradar.system.actions import system_action
from flugradar.system.update import LOG_FILE as _UPDATE_LOG_FILE
from flugradar.system.update import trigger_update_async

# Common OS captive-portal probe URLs -- redirecting them to /wifi-setup is
# what makes a phone pop its "sign in to network" browser automatically
# when it joins the setup hotspot. Best-effort: this only fires if the
# probe's DNS lookup actually resolves to us in the first place, which
# needs the dnsmasq-shared wildcard config install.sh writes
# (/etc/NetworkManager/dnsmasq-shared.d/) -- without it, the fixed URL
# shown on the display / QR follow-up text is the fallback.
_CAPTIVE_PORTAL_PROBES = [
    "/generate_204",          # Android
    "/gen_204",
    "/hotspot-detect.html",   # iOS / macOS
    "/library/test/success.html",
    "/connecttest.txt",       # Windows
    "/ncsi.txt",
    "/success.txt",           # Firefox
]

log = logging.getLogger(__name__)


def create_app(settings: AppSettings | None = None) -> Flask:
    if settings is None:
        settings = AppSettings()

    app = Flask(
        __name__,
        template_folder=os.path.join(os.path.dirname(__file__), "templates"),
        static_folder=os.path.join(os.path.dirname(__file__), "static"),
    )
    app.config["settings"] = settings

    # Rebuilt lazily rather than constructed once at startup, so a key
    # entered via the portal takes effect immediately instead of needing a
    # service restart -- the settings object is shared and mutated in
    # place by save_portal_settings(), but a client built once at
    # create_app() time would never see that change.
    _weather_state: dict[str, object] = {"client": None, "key": None, "lat": None, "lon": None}

    def _get_weather_client() -> WeatherClient | None:
        key = settings.tomorrow_api_key
        if not key:
            if _weather_state["client"]:
                _weather_state["client"].close()
                _weather_state["client"] = None
            return None
        if (
            _weather_state["client"] is None
            or _weather_state["key"] != key
            or _weather_state["lat"] != settings.home.lat
            or _weather_state["lon"] != settings.home.lon
        ):
            if _weather_state["client"]:
                _weather_state["client"].close()
            _weather_state["client"] = WeatherClient(
                api_key=key, lat=settings.home.lat, lon=settings.home.lon,
            )
            _weather_state["key"] = key
            _weather_state["lat"] = settings.home.lat
            _weather_state["lon"] = settings.home.lon
        return _weather_state["client"]

    @app.route("/")
    def index():
        return render_template("index.html", settings=settings, version=__version__)

    @app.route("/radar", methods=["GET", "POST"])
    def radar():
        if request.method == "POST":
            updates = {}
            for key in ("home_lat", "home_lon", "radius_km"):
                val = request.form.get(key)
                if val:
                    updates[key] = float(val)
            if unit := request.form.get("distance_unit"):
                updates["distance_unit"] = unit
            if alt := request.form.get("min_altitude_ft"):
                updates["min_altitude_ft"] = int(alt)
            if provider := request.form.get("map_provider"):
                updates["map_provider"] = provider
            updates["openaip_overlay_enabled"] = (
                request.form.get("openaip_overlay_enabled") is not None
            )
            updates["rainviewer_enabled"] = (
                request.form.get("rainviewer_enabled") is not None
            )
            if (v := request.form.get("map_brightness")) is not None:
                updates["map_brightness"] = int(v)
            updates["highlight_emergency"] = request.form.get("highlight_emergency") is not None
            updates["highlight_military"] = request.form.get("highlight_military") is not None
            updates["only_highlighted"] = request.form.get("only_highlighted") is not None
            # unlike the other text fields above, an empty submission here is
            # meaningful (it stops tracking), so it's not skipped like `home_lat` etc.
            updates["tracked_callsign"] = request.form.get("tracked_callsign", "").strip().upper()
            if (v := request.form.get("tracking_timeout_min")) is not None:
                updates["tracking_timeout_s"] = int(float(v) * 60)
            settings.save_portal_settings(updates)
            return redirect(url_for("radar", saved=1))
        return render_template("radar.html", settings=settings, locations=LOCATIONS)

    @app.route("/display", methods=["GET", "POST"])
    def display():
        if request.method == "POST":
            updates = {}
            if theme := request.form.get("theme"):
                updates["theme"] = theme
            if icon_set := request.form.get("aircraft_icon_set"):
                updates["aircraft_icon_set"] = icon_set
            if (v := request.form.get("auto_clock_s")) is not None:
                updates["auto_clock_s"] = int(v)
            updates["show_compass"] = request.form.get("show_compass") is not None
            updates["show_sweep"] = request.form.get("show_sweep") is not None
            updates["show_rings"] = request.form.get("show_rings") is not None
            updates["show_aircraft_tags"] = request.form.get("show_aircraft_tags") is not None
            if (v := request.form.get("brightness")) is not None:
                updates["brightness"] = int(v)
            updates["night_mode_enabled"] = request.form.get("night_mode_enabled") is not None
            if v := request.form.get("night_mode_start"):
                updates["night_mode_start"] = v
            if v := request.form.get("night_mode_end"):
                updates["night_mode_end"] = v
            if (v := request.form.get("night_mode_brightness")) is not None:
                updates["night_mode_brightness"] = int(v)
            if v := request.form.get("temperature_unit"):
                updates["temperature_unit"] = v
            if v := request.form.get("time_format"):
                updates["time_format"] = v
            settings.save_portal_settings(updates)
            return redirect(url_for("display", saved=1))
        return render_template("display.html", settings=settings)

    @app.route("/api-keys", methods=["GET", "POST"])
    def api_keys():
        if request.method == "POST":
            updates = {}
            for key in ("fr24_api_key", "tomorrow_api_key", "airlabs_api_key", "openaip_api_key"):
                val = request.form.get(key, "").strip()
                if val:
                    updates[key] = val
            updates["adsbdb_enabled"] = request.form.get("adsbdb_enabled") is not None
            if nearest := request.form.get("adsbdb_enrich_nearest"):
                updates["adsbdb_enrich_nearest"] = int(nearest)
            updates["aircraft_photos_enabled"] = (
                request.form.get("aircraft_photos_enabled") is not None
            )
            settings.save_portal_settings(updates)
            return redirect(url_for("api_keys", saved=1))
        return render_template("api_keys.html", settings=settings)

    @app.route("/system", methods=["GET", "POST"])
    def system():
        action = request.form.get("action") if request.method == "POST" else None
        message = None
        if action == "restart":
            message = "Neustart eingeleitet..."
            system_action("reboot")
        elif action == "shutdown":
            message = "Herunterfahren eingeleitet..."
            system_action("shutdown")
        elif action == "update":
            message = "Update im Hintergrund gestartet — unten in einer Minute nachsehen."
            trigger_update_async()
        return render_template(
            "system.html", settings=settings, version=__version__, message=message,
            update_log=_last_update_log_line(),
        )

    @app.route("/wifi-setup", methods=["GET", "POST"])
    def wifi_setup():
        message = None
        error = None
        if request.method == "POST":
            ssid = request.form.get("ssid", "").strip()
            password = request.form.get("password", "")
            if not ssid:
                error = "Bitte ein WLAN auswählen."
            else:
                ok, detail = network_watchdog.connect_to_wifi(ssid, password)
                if ok:
                    message = (
                        f"Verbindung zu {ssid} hergestellt. Der Setup-Hotspot wird "
                        "in Kürze beendet -- die Statusanzeige auf dem Gerät zeigt "
                        "das Ergebnis, sobald dieses Telefon die Verbindung verliert."
                    )
                else:
                    error = f"Verbindung zu {ssid} fehlgeschlagen: {detail or 'unbekannter Fehler'}"
                    # nmcli's connect attempt drops our own hotspot on the same
                    # radio even when it then fails -- bring it back up so this
                    # phone can retry instead of being stranded with no network.
                    cfg = network_watchdog.WatchdogConfig.from_env()
                    network_watchdog.start_hotspot(cfg.hotspot_ssid, cfg.hotspot_password)
        networks = network_watchdog.scan_networks()
        return render_template(
            "wifi_setup.html", networks=networks, message=message, error=error,
        )

    def _redirect_to_wifi_setup():
        return redirect(url_for("wifi_setup"))

    for _probe_path in _CAPTIVE_PORTAL_PROBES:
        app.add_url_rule(
            _probe_path,
            f"captive_probe_{_probe_path.strip('/').replace('/', '_')}",
            _redirect_to_wifi_setup,
        )

    @app.route("/weather")
    def weather():
        data = None
        forecast = []
        weather_client = _get_weather_client()
        if weather_client:
            data = weather_client.get_weather()
            forecast = weather_client.get_forecast(days=3)
        return render_template(
            "weather.html", settings=settings, weather=data, forecast=forecast,
            has_key=bool(settings.tomorrow_api_key),
        )

    @app.route("/about")
    def about():
        return render_template("about.html", version=__version__, settings=settings)

    @app.route("/api/weather", methods=["GET"])
    def api_weather():
        weather_client = _get_weather_client()
        if not weather_client:
            return jsonify({"error": "no API key configured"}), 404
        data = weather_client.get_weather()
        if not data:
            return jsonify({"error": "weather unavailable"}), 503
        return jsonify({
            "temperature_c": data.temperature_c,
            "condition": data.condition,
            "humidity": data.humidity,
            "wind_speed_ms": data.wind_speed_ms,
            "wind_direction_deg": data.wind_direction_deg,
            "visibility_km": data.visibility_km,
            "pressure_hpa": data.pressure_hpa,
            "cloud_cover_pct": data.cloud_cover_pct,
        })

    @app.route("/api/settings", methods=["GET"])
    def api_get_settings():
        return jsonify({
            "home_lat": settings.home.lat,
            "home_lon": settings.home.lon,
            "radius_km": settings.home.radius_km,
            "distance_unit": settings.distance_unit,
            "theme": settings.theme,
            "aircraft_icon_set": settings.aircraft_icon_set,
            "min_altitude_ft": settings.min_altitude_ft,
            "auto_clock_s": settings.auto_clock_s,
            "adsbdb_enabled": settings.adsbdb_enabled,
            "adsbdb_enrich_nearest": settings.adsbdb_enrich_nearest,
            "aircraft_photos_enabled": settings.aircraft_photos_enabled,
            "openaip_overlay_enabled": settings.openaip_overlay_enabled,
            "map_provider": settings.map_provider,
            "rainviewer_enabled": settings.rainviewer_enabled,
        })

    @app.route("/api/settings", methods=["POST"])
    def api_set_settings():
        data = request.get_json(force=True)
        settings.save_portal_settings(data)
        return jsonify({"status": "ok"})

    return app


def _last_update_log_line() -> str | None:
    try:
        lines = _UPDATE_LOG_FILE.read_text().strip().splitlines()
    except OSError:
        return None
    return lines[-1] if lines else None
