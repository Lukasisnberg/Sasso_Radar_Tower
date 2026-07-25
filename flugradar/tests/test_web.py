"""Tests for the Flask web portal."""

import json
from unittest.mock import MagicMock

import pytest

from flugradar.config import settings as settings_mod
from flugradar.config.settings import AppSettings
from flugradar.web.app import create_app


@pytest.fixture()
def client(monkeypatch, tmp_path):
    portal_file = tmp_path / "settings.json"
    monkeypatch.setattr(settings_mod, "PORTAL_SETTINGS_FILE", portal_file)
    settings = AppSettings()
    app = create_app(settings)
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


class TestPages:
    def test_index(self, client):
        r = client.get("/")
        assert r.status_code == 200
        assert b"Sasso Radar Tower" in r.data

    def test_radar_get(self, client):
        r = client.get("/radar")
        assert r.status_code == 200
        assert b"Latitude" in r.data

    def test_display_get(self, client):
        r = client.get("/display")
        assert r.status_code == 200
        assert b"Theme" in r.data

    def test_api_keys_get(self, client):
        r = client.get("/api-keys")
        assert r.status_code == 200
        assert b"FR24" in r.data

    def test_system_get(self, client):
        r = client.get("/system")
        assert r.status_code == 200
        assert b"Restart" in r.data

    def test_about_get(self, client):
        r = client.get("/about")
        assert r.status_code == 200
        assert b"adsb.fi" in r.data

    def test_weather_get_no_key(self, client):
        r = client.get("/weather")
        assert r.status_code == 200
        assert b"No Tomorrow.io API key" in r.data

    def test_weather_api_no_key(self, client):
        r = client.get("/api/weather")
        assert r.status_code == 404


class TestWeatherKeyLiveReload:
    """Regression test: /weather and /api/weather used to build their
    WeatherClient exactly once, at create_app() time -- so a key saved
    via the /api-keys form updated settings.tomorrow_api_key in memory,
    but the routes kept using the stale (usually None) client until the
    web service was restarted. They now rebuild lazily off the live
    settings object instead."""

    def test_saving_key_makes_weather_page_pick_it_up_without_restart(self, monkeypatch, client):
        fake_client = MagicMock()
        fake_client.get_weather.return_value = None
        fake_client.get_forecast.return_value = []
        monkeypatch.setattr("flugradar.web.app.WeatherClient", MagicMock(return_value=fake_client))

        r = client.get("/weather")
        assert b"No Tomorrow.io API key" in r.data

        client.post("/api-keys", data={"tomorrow_api_key": "newkey"})

        r = client.get("/weather")
        assert b"No Tomorrow.io API key" not in r.data
        assert b"Weather data currently unavailable" in r.data

    def test_saving_key_makes_api_weather_pick_it_up_without_restart(self, monkeypatch, client):
        from flugradar.data_sources.weather import WeatherData
        fake_client = MagicMock()
        fake_client.get_weather.return_value = WeatherData(temperature_c=20.0, condition="Clear")
        monkeypatch.setattr("flugradar.web.app.WeatherClient", MagicMock(return_value=fake_client))

        assert client.get("/api/weather").status_code == 404

        client.post("/api-keys", data={"tomorrow_api_key": "newkey"})

        r = client.get("/api/weather")
        assert r.status_code == 200
        assert r.get_json()["temperature_c"] == 20.0


class TestRadarPost:
    def test_save_location(self, client, monkeypatch, tmp_path):
        portal_file = tmp_path / "settings.json"
        monkeypatch.setattr(settings_mod, "PORTAL_SETTINGS_FILE", portal_file)
        r = client.post("/radar", data={
            "home_lat": "48.8566",
            "home_lon": "2.3522",
            "radius_km": "80",
            "distance_unit": "nm",
            "min_altitude_ft": "500",
        }, follow_redirects=False)
        assert r.status_code == 302
        data = json.loads(portal_file.read_text())
        assert data["home_lat"] == 48.8566
        assert data["distance_unit"] == "nm"

    def test_save_map_provider(self, client, monkeypatch, tmp_path):
        portal_file = tmp_path / "settings.json"
        monkeypatch.setattr(settings_mod, "PORTAL_SETTINGS_FILE", portal_file)
        r = client.post("/radar", data={"map_provider": "osm"}, follow_redirects=False)
        assert r.status_code == 302
        data = json.loads(portal_file.read_text())
        assert data["map_provider"] == "osm"

    def test_openaip_overlay_checkbox_present(self, client, monkeypatch, tmp_path):
        portal_file = tmp_path / "settings.json"
        monkeypatch.setattr(settings_mod, "PORTAL_SETTINGS_FILE", portal_file)
        r = client.post(
            "/radar", data={"openaip_overlay_enabled": "1"}, follow_redirects=False
        )
        assert r.status_code == 302
        data = json.loads(portal_file.read_text())
        assert data["openaip_overlay_enabled"] is True

    def test_openaip_overlay_checkbox_absent_means_disabled(self, client, monkeypatch, tmp_path):
        portal_file = tmp_path / "settings.json"
        monkeypatch.setattr(settings_mod, "PORTAL_SETTINGS_FILE", portal_file)
        r = client.post("/radar", data={}, follow_redirects=False)
        assert r.status_code == 302
        data = json.loads(portal_file.read_text())
        assert data["openaip_overlay_enabled"] is False

    def test_rainviewer_checkbox_present(self, client, monkeypatch, tmp_path):
        portal_file = tmp_path / "settings.json"
        monkeypatch.setattr(settings_mod, "PORTAL_SETTINGS_FILE", portal_file)
        r = client.post("/radar", data={"rainviewer_enabled": "1"}, follow_redirects=False)
        assert r.status_code == 302
        data = json.loads(portal_file.read_text())
        assert data["rainviewer_enabled"] is True

    def test_rainviewer_checkbox_absent_means_disabled(self, client, monkeypatch, tmp_path):
        portal_file = tmp_path / "settings.json"
        monkeypatch.setattr(settings_mod, "PORTAL_SETTINGS_FILE", portal_file)
        r = client.post("/radar", data={}, follow_redirects=False)
        assert r.status_code == 302
        data = json.loads(portal_file.read_text())
        assert data["rainviewer_enabled"] is False

    def test_map_brightness(self, client, monkeypatch, tmp_path):
        portal_file = tmp_path / "settings.json"
        monkeypatch.setattr(settings_mod, "PORTAL_SETTINGS_FILE", portal_file)
        r = client.post("/radar", data={"map_brightness": "70"}, follow_redirects=False)
        assert r.status_code == 302
        data = json.loads(portal_file.read_text())
        assert data["map_brightness"] == 70

    def test_highlight_and_only_highlighted_checkboxes(self, client, monkeypatch, tmp_path):
        portal_file = tmp_path / "settings.json"
        monkeypatch.setattr(settings_mod, "PORTAL_SETTINGS_FILE", portal_file)
        r = client.post(
            "/radar",
            data={"highlight_emergency": "1", "only_highlighted": "1"},
            follow_redirects=False,
        )
        assert r.status_code == 302
        data = json.loads(portal_file.read_text())
        assert data["highlight_emergency"] is True
        assert data["highlight_military"] is False  # omitted checkbox -> unchecked
        assert data["only_highlighted"] is True

    def test_locations_passed_to_template_match_device_menu(self, client):
        r = client.get("/radar")
        assert b"Sassofortino" in r.data
        assert b"Gie\xc3\x9fen" in r.data or b"Gie&#223;en" in r.data or "Gießen".encode() in r.data

    def test_set_tracked_callsign(self, client, monkeypatch, tmp_path):
        portal_file = tmp_path / "settings.json"
        monkeypatch.setattr(settings_mod, "PORTAL_SETTINGS_FILE", portal_file)
        r = client.post(
            "/radar", data={"tracked_callsign": "dlh400"}, follow_redirects=False,
        )
        assert r.status_code == 302
        data = json.loads(portal_file.read_text())
        assert data["tracked_callsign"] == "DLH400"  # normalised uppercase

    def test_empty_tracked_callsign_clears_tracking(self, client, monkeypatch, tmp_path):
        portal_file = tmp_path / "settings.json"
        monkeypatch.setattr(settings_mod, "PORTAL_SETTINGS_FILE", portal_file)
        client.post("/radar", data={"tracked_callsign": "DLH400"}, follow_redirects=False)
        r = client.post("/radar", data={}, follow_redirects=False)
        assert r.status_code == 302
        data = json.loads(portal_file.read_text())
        assert data["tracked_callsign"] == ""

    def test_tracking_timeout_minutes_converted_to_seconds(self, client, monkeypatch, tmp_path):
        portal_file = tmp_path / "settings.json"
        monkeypatch.setattr(settings_mod, "PORTAL_SETTINGS_FILE", portal_file)
        r = client.post(
            "/radar", data={"tracking_timeout_min": "20"}, follow_redirects=False,
        )
        assert r.status_code == 302
        data = json.loads(portal_file.read_text())
        assert data["tracking_timeout_s"] == 1200


class TestDisplayPost:
    def test_save_theme(self, client, monkeypatch, tmp_path):
        portal_file = tmp_path / "settings.json"
        monkeypatch.setattr(settings_mod, "PORTAL_SETTINGS_FILE", portal_file)
        r = client.post("/display", data={"theme": "amber"}, follow_redirects=False)
        assert r.status_code == 302
        data = json.loads(portal_file.read_text())
        assert data["theme"] == "amber"

    def test_save_aircraft_icon_set(self, client, monkeypatch, tmp_path):
        portal_file = tmp_path / "settings.json"
        monkeypatch.setattr(settings_mod, "PORTAL_SETTINGS_FILE", portal_file)
        r = client.post(
            "/display", data={"aircraft_icon_set": "simple"}, follow_redirects=False
        )
        assert r.status_code == 302
        data = json.loads(portal_file.read_text())
        assert data["aircraft_icon_set"] == "simple"

    def test_radar_element_toggles(self, client, monkeypatch, tmp_path):
        portal_file = tmp_path / "settings.json"
        monkeypatch.setattr(settings_mod, "PORTAL_SETTINGS_FILE", portal_file)
        r = client.post("/display", data={"show_compass": "1"}, follow_redirects=False)
        assert r.status_code == 302
        data = json.loads(portal_file.read_text())
        assert data["show_compass"] is True
        assert data["show_sweep"] is False  # omitted checkbox -> unchecked
        assert data["show_aircraft_tags"] is False

    def test_brightness_and_night_mode(self, client, monkeypatch, tmp_path):
        portal_file = tmp_path / "settings.json"
        monkeypatch.setattr(settings_mod, "PORTAL_SETTINGS_FILE", portal_file)
        r = client.post(
            "/display",
            data={
                "brightness": "60",
                "night_mode_enabled": "1",
                "night_mode_start": "23:00",
                "night_mode_end": "07:00",
                "night_mode_brightness": "20",
            },
            follow_redirects=False,
        )
        assert r.status_code == 302
        data = json.loads(portal_file.read_text())
        assert data["brightness"] == 60
        assert data["night_mode_enabled"] is True
        assert data["night_mode_start"] == "23:00"
        assert data["night_mode_end"] == "07:00"
        assert data["night_mode_brightness"] == 20

    def test_units(self, client, monkeypatch, tmp_path):
        portal_file = tmp_path / "settings.json"
        monkeypatch.setattr(settings_mod, "PORTAL_SETTINGS_FILE", portal_file)
        r = client.post(
            "/display",
            data={"temperature_unit": "f", "time_format": "12h"},
            follow_redirects=False,
        )
        assert r.status_code == 302
        data = json.loads(portal_file.read_text())
        assert data["temperature_unit"] == "f"
        assert data["time_format"] == "12h"


class TestApiKeysPost:
    def test_save_adsbdb_settings(self, client, monkeypatch, tmp_path):
        portal_file = tmp_path / "settings.json"
        monkeypatch.setattr(settings_mod, "PORTAL_SETTINGS_FILE", portal_file)
        r = client.post(
            "/api-keys",
            data={"adsbdb_enrich_nearest": "5", "aircraft_photos_enabled": "1"},
            follow_redirects=False,
        )
        assert r.status_code == 302
        data = json.loads(portal_file.read_text())
        assert data["adsbdb_enrich_nearest"] == 5
        assert data["aircraft_photos_enabled"] is True
        assert data["adsbdb_enabled"] is False  # checkbox omitted => unchecked

    def test_adsbdb_enabled_checkbox_present(self, client, monkeypatch, tmp_path):
        portal_file = tmp_path / "settings.json"
        monkeypatch.setattr(settings_mod, "PORTAL_SETTINGS_FILE", portal_file)
        r = client.post(
            "/api-keys", data={"adsbdb_enabled": "1"}, follow_redirects=False,
        )
        assert r.status_code == 302
        data = json.loads(portal_file.read_text())
        assert data["adsbdb_enabled"] is True

    def test_save_openaip_api_key(self, client, monkeypatch, tmp_path):
        portal_file = tmp_path / "settings.json"
        monkeypatch.setattr(settings_mod, "PORTAL_SETTINGS_FILE", portal_file)
        r = client.post(
            "/api-keys", data={"openaip_api_key": "my-openaip-key"}, follow_redirects=False,
        )
        assert r.status_code == 302
        data = json.loads(portal_file.read_text())
        assert data["openaip_api_key"] == "my-openaip-key"


class TestSystemUpdate:
    def test_update_button_triggers_async_update(self, client, monkeypatch):
        mock_trigger = MagicMock()
        monkeypatch.setattr("flugradar.web.app.trigger_update_async", mock_trigger)
        r = client.post("/system", data={"action": "update"})
        assert r.status_code == 200
        mock_trigger.assert_called_once_with()
        assert b"Update" in r.data

    def test_update_does_not_trigger_on_plain_get(self, client, monkeypatch):
        mock_trigger = MagicMock()
        monkeypatch.setattr("flugradar.web.app.trigger_update_async", mock_trigger)
        client.get("/system")
        mock_trigger.assert_not_called()

    def test_shows_last_update_log_line(self, client, monkeypatch, tmp_path):
        log_file = tmp_path / "update.log"
        log_file.write_text("2026-07-25T12:00:00 OK: already up to date\n")
        monkeypatch.setattr("flugradar.web.app._UPDATE_LOG_FILE", log_file)
        r = client.get("/system")
        assert b"already up to date" in r.data

    def test_no_log_file_yet_does_not_crash(self, client, monkeypatch, tmp_path):
        monkeypatch.setattr("flugradar.web.app._UPDATE_LOG_FILE", tmp_path / "missing.log")
        r = client.get("/system")
        assert r.status_code == 200


class TestRestApi:
    def test_get_settings(self, client):
        r = client.get("/api/settings")
        assert r.status_code == 200
        data = r.get_json()
        assert "home_lat" in data
        assert "theme" in data
        assert data["distance_unit"] == "km"

    def test_post_settings(self, client, monkeypatch, tmp_path):
        portal_file = tmp_path / "settings.json"
        monkeypatch.setattr(settings_mod, "PORTAL_SETTINGS_FILE", portal_file)
        r = client.post(
            "/api/settings",
            data=json.dumps({"radius_km": 200}),
            content_type="application/json",
        )
        assert r.status_code == 200
        assert r.get_json()["status"] == "ok"
        data = json.loads(portal_file.read_text())
        assert data["radius_km"] == 200
