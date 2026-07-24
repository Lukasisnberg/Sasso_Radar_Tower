"""Tests for the Flask web portal."""

import json

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

    def test_openaip_overlay_checkbox_present(self, client, monkeypatch, tmp_path):
        portal_file = tmp_path / "settings.json"
        monkeypatch.setattr(settings_mod, "PORTAL_SETTINGS_FILE", portal_file)
        r = client.post(
            "/display", data={"openaip_overlay_enabled": "1"}, follow_redirects=False
        )
        assert r.status_code == 302
        data = json.loads(portal_file.read_text())
        assert data["openaip_overlay_enabled"] is True

    def test_openaip_overlay_checkbox_absent_means_disabled(self, client, monkeypatch, tmp_path):
        portal_file = tmp_path / "settings.json"
        monkeypatch.setattr(settings_mod, "PORTAL_SETTINGS_FILE", portal_file)
        r = client.post("/display", data={}, follow_redirects=False)
        assert r.status_code == 302
        data = json.loads(portal_file.read_text())
        assert data["openaip_overlay_enabled"] is False


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
