"""Unit tests for the configuration priority logic."""

import json
import os
import tempfile

import pytest

from flugradar.config import settings as settings_mod
from flugradar.config.settings import AppSettings


class TestEnvOverrides:
    def test_lat_lon_from_env(self, monkeypatch):
        monkeypatch.setenv("FLUGRADAR_HOME_LAT", "52.52")
        monkeypatch.setenv("FLUGRADAR_HOME_LON", "13.405")
        s = AppSettings()
        assert s.home.lat == pytest.approx(52.52)
        assert s.home.lon == pytest.approx(13.405)

    def test_radius_from_env(self, monkeypatch):
        monkeypatch.setenv("FLUGRADAR_RADIUS_KM", "200")
        s = AppSettings()
        assert s.home.radius_km == 200.0

    def test_distance_unit_from_env(self, monkeypatch):
        monkeypatch.setenv("FLUGRADAR_DISTANCE_UNIT", "nm")
        s = AppSettings()
        assert s.distance_unit == "nm"

    def test_aircraft_icon_set_from_env(self, monkeypatch):
        monkeypatch.setenv("FLUGRADAR_AIRCRAFT_ICON_SET", "simple")
        s = AppSettings()
        assert s.aircraft_icon_set == "simple"

    def test_adsbdb_enabled_from_env(self, monkeypatch):
        monkeypatch.setenv("ADSBDB_ENABLED", "false")
        s = AppSettings()
        assert s.adsbdb_enabled is False

    def test_adsbdb_enrich_nearest_from_env(self, monkeypatch):
        monkeypatch.setenv("ADSBDB_ENRICH_NEAREST", "25")
        s = AppSettings()
        assert s.adsbdb_enrich_nearest == 25

    def test_aircraft_photos_enabled_from_env(self, monkeypatch):
        monkeypatch.setenv("AIRCRAFT_PHOTOS_ENABLED", "true")
        s = AppSettings()
        assert s.aircraft_photos_enabled is True


class TestPortalSettings:
    def test_portal_overrides_defaults(self, monkeypatch, tmp_path):
        portal_file = tmp_path / "settings.json"
        portal_file.write_text(json.dumps({
            "home_lat": 48.8566,
            "home_lon": 2.3522,
            "radius_km": 50,
        }))
        monkeypatch.setattr(settings_mod, "PORTAL_SETTINGS_FILE", portal_file)
        s = AppSettings()
        assert s.home.lat == pytest.approx(48.8566)
        assert s.home.lon == pytest.approx(2.3522)
        assert s.home.radius_km == 50.0

    def test_env_wins_over_portal(self, monkeypatch, tmp_path):
        portal_file = tmp_path / "settings.json"
        portal_file.write_text(json.dumps({"home_lat": 48.0}))
        monkeypatch.setattr(settings_mod, "PORTAL_SETTINGS_FILE", portal_file)
        monkeypatch.setenv("FLUGRADAR_HOME_LAT", "52.0")
        s = AppSettings()
        assert s.home.lat == pytest.approx(52.0)

    def test_missing_portal_file(self, monkeypatch, tmp_path):
        monkeypatch.setattr(
            settings_mod, "PORTAL_SETTINGS_FILE", tmp_path / "nonexistent.json"
        )
        s = AppSettings()
        assert s.home.lat == pytest.approx(47.3769)  # default

    def test_save_portal_settings(self, monkeypatch, tmp_path):
        portal_file = tmp_path / "settings.json"
        monkeypatch.setattr(settings_mod, "PORTAL_SETTINGS_FILE", portal_file)
        s = AppSettings()
        s.save_portal_settings({"home_lat": 51.0, "home_lon": 0.0})
        data = json.loads(portal_file.read_text())
        assert data["home_lat"] == 51.0
        assert data["home_lon"] == 0.0

    def test_save_updates_instance_in_memory(self, monkeypatch, tmp_path):
        portal_file = tmp_path / "settings.json"
        monkeypatch.setattr(settings_mod, "PORTAL_SETTINGS_FILE", portal_file)
        s = AppSettings()
        assert s.theme == "dark"
        s.save_portal_settings({"theme": "amber"})
        assert s.theme == "amber"
        assert s.home.lat == pytest.approx(47.3769)

    def test_save_updates_aircraft_icon_set_in_memory(self, monkeypatch, tmp_path):
        portal_file = tmp_path / "settings.json"
        monkeypatch.setattr(settings_mod, "PORTAL_SETTINGS_FILE", portal_file)
        s = AppSettings()
        assert s.aircraft_icon_set == "detailed"
        s.save_portal_settings({"aircraft_icon_set": "simple"})
        assert s.aircraft_icon_set == "simple"

    def test_adsbdb_defaults(self, monkeypatch, tmp_path):
        monkeypatch.setattr(settings_mod, "PORTAL_SETTINGS_FILE", tmp_path / "nonexistent.json")
        s = AppSettings()
        assert s.adsbdb_enabled is True
        assert s.adsbdb_enrich_nearest == 10
        assert s.aircraft_photos_enabled is False

    def test_save_updates_adsbdb_settings_in_memory(self, monkeypatch, tmp_path):
        portal_file = tmp_path / "settings.json"
        monkeypatch.setattr(settings_mod, "PORTAL_SETTINGS_FILE", portal_file)
        s = AppSettings()
        s.save_portal_settings({
            "adsbdb_enabled": False,
            "adsbdb_enrich_nearest": 3,
            "aircraft_photos_enabled": True,
        })
        assert s.adsbdb_enabled is False
        assert s.adsbdb_enrich_nearest == 3
        assert s.aircraft_photos_enabled is True

    def test_save_updates_home_location_in_memory(self, monkeypatch, tmp_path):
        portal_file = tmp_path / "settings.json"
        monkeypatch.setattr(settings_mod, "PORTAL_SETTINGS_FILE", portal_file)
        s = AppSettings()
        s.save_portal_settings({"home_lat": 52.52, "radius_km": 200})
        assert s.home.lat == pytest.approx(52.52)
        assert s.home.radius_km == 200.0


class TestLiveReload:
    def test_no_change_returns_false(self, monkeypatch, tmp_path):
        portal_file = tmp_path / "settings.json"
        portal_file.write_text(json.dumps({"theme": "dark"}))
        monkeypatch.setattr(settings_mod, "PORTAL_SETTINGS_FILE", portal_file)
        s = AppSettings()
        assert s.check_portal_reload() is False

    def test_file_change_returns_true(self, monkeypatch, tmp_path):
        portal_file = tmp_path / "settings.json"
        portal_file.write_text(json.dumps({"theme": "dark"}))
        monkeypatch.setattr(settings_mod, "PORTAL_SETTINGS_FILE", portal_file)
        s = AppSettings()

        os.utime(portal_file, (0, 0))
        portal_file.write_text(json.dumps({"theme": "amber"}))
        assert s.check_portal_reload() is True
        assert s.theme == "amber"

    def test_reload_applies_new_values(self, monkeypatch, tmp_path):
        portal_file = tmp_path / "settings.json"
        portal_file.write_text(json.dumps({"home_lat": 48.0, "radius_km": 50}))
        monkeypatch.setattr(settings_mod, "PORTAL_SETTINGS_FILE", portal_file)
        s = AppSettings()
        assert s.home.lat == pytest.approx(48.0)

        os.utime(portal_file, (0, 0))
        portal_file.write_text(json.dumps({"home_lat": 52.0, "radius_km": 200}))
        s.check_portal_reload()
        assert s.home.lat == pytest.approx(52.0)
        assert s.home.radius_km == 200.0

    def test_reload_env_still_wins(self, monkeypatch, tmp_path):
        portal_file = tmp_path / "settings.json"
        portal_file.write_text(json.dumps({"home_lat": 48.0}))
        monkeypatch.setattr(settings_mod, "PORTAL_SETTINGS_FILE", portal_file)
        monkeypatch.setenv("FLUGRADAR_HOME_LAT", "52.0")
        s = AppSettings()
        assert s.home.lat == pytest.approx(52.0)

        os.utime(portal_file, (0, 0))
        portal_file.write_text(json.dumps({"home_lat": 40.0}))
        s.check_portal_reload()
        assert s.home.lat == pytest.approx(52.0)

    def test_reload_applies_aircraft_icon_set(self, monkeypatch, tmp_path):
        portal_file = tmp_path / "settings.json"
        portal_file.write_text(json.dumps({"aircraft_icon_set": "detailed"}))
        monkeypatch.setattr(settings_mod, "PORTAL_SETTINGS_FILE", portal_file)
        s = AppSettings()
        assert s.aircraft_icon_set == "detailed"

        os.utime(portal_file, (0, 0))
        portal_file.write_text(json.dumps({"aircraft_icon_set": "simple"}))
        assert s.check_portal_reload() is True
        assert s.aircraft_icon_set == "simple"

    def test_reload_applies_adsbdb_settings(self, monkeypatch, tmp_path):
        portal_file = tmp_path / "settings.json"
        portal_file.write_text(json.dumps({"adsbdb_enabled": True}))
        monkeypatch.setattr(settings_mod, "PORTAL_SETTINGS_FILE", portal_file)
        s = AppSettings()
        assert s.adsbdb_enabled is True

        os.utime(portal_file, (0, 0))
        portal_file.write_text(json.dumps({"adsbdb_enabled": False, "adsbdb_enrich_nearest": 2}))
        assert s.check_portal_reload() is True
        assert s.adsbdb_enabled is False
        assert s.adsbdb_enrich_nearest == 2

    def test_reload_missing_file(self, monkeypatch, tmp_path):
        portal_file = tmp_path / "settings.json"
        portal_file.write_text(json.dumps({"theme": "amber"}))
        monkeypatch.setattr(settings_mod, "PORTAL_SETTINGS_FILE", portal_file)
        s = AppSettings()
        assert s.theme == "amber"

        portal_file.unlink()
        assert s.check_portal_reload() is True
        assert s.theme == "dark"

    def test_no_reload_when_mtime_unchanged(self, monkeypatch, tmp_path):
        portal_file = tmp_path / "settings.json"
        portal_file.write_text(json.dumps({"theme": "dark"}))
        monkeypatch.setattr(settings_mod, "PORTAL_SETTINGS_FILE", portal_file)
        s = AppSettings()
        assert s.check_portal_reload() is False
        assert s.check_portal_reload() is False
