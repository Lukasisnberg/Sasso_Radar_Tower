"""Flask web portal for remote configuration of Sasso Radar Tower."""

import json
import logging
import os
import subprocess

from flask import Flask, render_template, request, jsonify, redirect, url_for

from flugradar import __version__
from flugradar.config.settings import AppSettings, PORTAL_SETTINGS_FILE

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
            settings.save_portal_settings(updates)
            return redirect(url_for("radar", saved=1))
        return render_template("radar.html", settings=settings)

    @app.route("/display", methods=["GET", "POST"])
    def display():
        if request.method == "POST":
            updates = {}
            if theme := request.form.get("theme"):
                updates["theme"] = theme
            settings.save_portal_settings(updates)
            return redirect(url_for("display", saved=1))
        return render_template("display.html", settings=settings)

    @app.route("/api-keys", methods=["GET", "POST"])
    def api_keys():
        if request.method == "POST":
            updates = {}
            for key in ("fr24_api_key", "tomorrow_api_key", "airlabs_api_key"):
                val = request.form.get(key, "").strip()
                if val:
                    updates[key] = val
            settings.save_portal_settings(updates)
            return redirect(url_for("api_keys", saved=1))
        return render_template("api_keys.html", settings=settings)

    @app.route("/system", methods=["GET", "POST"])
    def system():
        action = request.form.get("action") if request.method == "POST" else None
        message = None
        if action == "restart":
            message = "Restart initiated..."
            _safe_system_action("reboot")
        elif action == "shutdown":
            message = "Shutdown initiated..."
            _safe_system_action("shutdown")
        return render_template(
            "system.html", settings=settings, version=__version__, message=message
        )

    @app.route("/about")
    def about():
        return render_template("about.html", version=__version__)

    @app.route("/api/settings", methods=["GET"])
    def api_get_settings():
        return jsonify({
            "home_lat": settings.home.lat,
            "home_lon": settings.home.lon,
            "radius_km": settings.home.radius_km,
            "distance_unit": settings.distance_unit,
            "theme": settings.theme,
            "min_altitude_ft": settings.min_altitude_ft,
        })

    @app.route("/api/settings", methods=["POST"])
    def api_set_settings():
        data = request.get_json(force=True)
        settings.save_portal_settings(data)
        return jsonify({"status": "ok"})

    return app


def _safe_system_action(action: str) -> None:
    try:
        if action == "reboot":
            subprocess.Popen(["sudo", "reboot"])
        elif action == "shutdown":
            subprocess.Popen(["sudo", "shutdown", "-h", "now"])
    except Exception:
        log.exception("System action '%s' failed", action)
