"""Unit tests for the adsb.fi client with mocked HTTP responses."""

import json
import time

import pytest
import responses

from flugradar.config.settings import AdsbConfig, HomeLocation
from flugradar.data_sources.adsb_fi import AdsbFiClient

SAMPLE_RESPONSE = {
    "aircraft": [
        {
            "hex": "4b1812",
            "flight": "SWR123 ",
            "lat": 47.5,
            "lon": 8.6,
            "alt_baro": 35000,
            "gs": 450.0,
            "track": 270.0,
            "baro_rate": -500,
            "squawk": "1000",
            "r": "HB-JBA",
            "t": "A320",
            "seen": 1.2,
            "category": "A3",
        },
        {
            "hex": "3c6589",
            "flight": "DLH456 ",
            "lat": 47.2,
            "lon": 8.3,
            "alt_baro": 28000,
            "gs": 410.0,
            "track": 90.0,
            "baro_rate": 0,
            "squawk": "7700",
            "r": "D-AIBC",
            "t": "A321",
            "seen": 0.5,
            "category": "A3",
        },
        {
            "hex": "000000",
            "lat": None,
            "lon": None,
        },
    ],
    "total": 3,
    "now": 1700000000.0,
}


@pytest.fixture
def home():
    return HomeLocation(lat=47.3769, lon=8.5417, radius_km=100)


@pytest.fixture
def adsb_cfg():
    return AdsbConfig(
        base_url="https://opendata.adsb.fi/api/v2",
        poll_interval_s=3.0,
        cache_ttl_s=2.0,
        request_timeout_s=5.0,
    )


@pytest.fixture
def client(adsb_cfg, home):
    c = AdsbFiClient(adsb_cfg, home)
    yield c
    c.close()


class TestAdsbFiClient:
    @responses.activate
    def test_fetch_parses_aircraft(self, client):
        responses.add(
            responses.GET,
            "https://opendata.adsb.fi/api/v2/lat/47.3769/lon/8.5417/dist/54",
            json=SAMPLE_RESPONSE,
            status=200,
        )
        aircraft = client.get_aircraft(force_refresh=True)
        assert len(aircraft) == 2  # third entry has no lat/lon

    @responses.activate
    def test_aircraft_fields(self, client):
        responses.add(
            responses.GET,
            "https://opendata.adsb.fi/api/v2/lat/47.3769/lon/8.5417/dist/54",
            json=SAMPLE_RESPONSE,
            status=200,
        )
        aircraft = client.get_aircraft(force_refresh=True)
        swr = next(ac for ac in aircraft if ac.callsign == "SWR123")
        assert swr.icao_hex == "4b1812"
        assert swr.altitude_ft == 35000
        assert swr.ground_speed_kt == 450.0
        assert swr.track_deg == 270.0
        assert swr.registration == "HB-JBA"
        assert swr.aircraft_type == "A320"
        assert swr.distance_km is not None
        assert swr.bearing_deg is not None

    @responses.activate
    def test_emergency_flag(self, client):
        responses.add(
            responses.GET,
            "https://opendata.adsb.fi/api/v2/lat/47.3769/lon/8.5417/dist/54",
            json=SAMPLE_RESPONSE,
            status=200,
        )
        aircraft = client.get_aircraft(force_refresh=True)
        dlh = next(ac for ac in aircraft if ac.callsign == "DLH456")
        assert dlh.is_emergency is True
        assert dlh.squawk == "7700"

    @responses.activate
    def test_sorted_by_distance(self, client):
        responses.add(
            responses.GET,
            "https://opendata.adsb.fi/api/v2/lat/47.3769/lon/8.5417/dist/54",
            json=SAMPLE_RESPONSE,
            status=200,
        )
        aircraft = client.get_aircraft(force_refresh=True)
        distances = [ac.distance_km for ac in aircraft]
        assert distances == sorted(distances)

    @responses.activate
    def test_cache_returns_stale_on_error(self, client):
        responses.add(
            responses.GET,
            "https://opendata.adsb.fi/api/v2/lat/47.3769/lon/8.5417/dist/54",
            json=SAMPLE_RESPONSE,
            status=200,
        )
        first = client.get_aircraft(force_refresh=True)
        assert len(first) == 2

        responses.replace(
            responses.GET,
            "https://opendata.adsb.fi/api/v2/lat/47.3769/lon/8.5417/dist/54",
            body=ConnectionError("network down"),
        )
        client._cache_ts = 0  # expire cache
        second = client.get_aircraft(force_refresh=True)
        assert len(second) == 2  # returns cached data

    @responses.activate
    def test_cache_hit_no_request(self, client):
        responses.add(
            responses.GET,
            "https://opendata.adsb.fi/api/v2/lat/47.3769/lon/8.5417/dist/54",
            json=SAMPLE_RESPONSE,
            status=200,
        )
        client.get_aircraft(force_refresh=True)
        assert len(responses.calls) == 1

        cached = client.get_aircraft(force_refresh=False)
        assert len(cached) == 2
        assert len(responses.calls) == 1  # no second request


class TestResponseFieldName:
    """Ensure the parser reads from 'aircraft', not 'ac'."""

    @responses.activate
    def test_ignores_ac_field(self, client):
        wrong_key_response = {
            "ac": [
                {"hex": "aaaaaa", "lat": 47.5, "lon": 8.6, "alt_baro": 30000},
            ],
            "total": 1,
            "now": 1700000000.0,
        }
        responses.add(
            responses.GET,
            "https://opendata.adsb.fi/api/v2/lat/47.3769/lon/8.5417/dist/54",
            json=wrong_key_response,
            status=200,
        )
        aircraft = client.get_aircraft(force_refresh=True)
        assert len(aircraft) == 0

    @responses.activate
    def test_reads_aircraft_field(self, client):
        correct_response = {
            "aircraft": [
                {"hex": "bbbbbb", "lat": 47.5, "lon": 8.6, "alt_baro": 30000},
            ],
            "total": 1,
            "now": 1700000000.0,
        }
        responses.add(
            responses.GET,
            "https://opendata.adsb.fi/api/v2/lat/47.3769/lon/8.5417/dist/54",
            json=correct_response,
            status=200,
        )
        aircraft = client.get_aircraft(force_refresh=True)
        assert len(aircraft) == 1
        assert aircraft[0].icao_hex == "bbbbbb"


class TestDisplayLabel:
    def test_callsign_preferred(self):
        from flugradar.data_sources.models import Aircraft
        ac = Aircraft(icao_hex="abc123", callsign="SWR1")
        assert ac.display_label == "SWR1"

    def test_registration_fallback(self):
        from flugradar.data_sources.models import Aircraft
        ac = Aircraft(icao_hex="abc123", registration="HB-JBA")
        assert ac.display_label == "HB-JBA"

    def test_hex_fallback(self):
        from flugradar.data_sources.models import Aircraft
        ac = Aircraft(icao_hex="abc123")
        assert ac.display_label == "abc123"
