"""Unit tests for the adsbdb.com enrichment client. All requests mocked."""

import time
from unittest.mock import MagicMock, patch

import pytest
import requests

from flugradar.data_sources.adsbdb import AdsbdbClient


def _resp(status_code=200, json_data=None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    if status_code >= 400:
        resp.raise_for_status.side_effect = requests.HTTPError(f"{status_code}")
    else:
        resp.raise_for_status = MagicMock()
    return resp


_FULL_RESPONSE = {
    "response": {
        "aircraft": {
            "type": "C Series 300",
            "icao_type": "BCS3",
            "manufacturer": "Bombardier",
            "mode_s": "4B1805",
            "registration": "HB-JCN",
            "registered_owner": "Swiss International Air Lines",
            "registered_owner_country_name": "Switzerland",
            "registered_owner_country_iso_name": "CH",
            "registered_owner_operator_flag_code": "SWR",
            "url_photo": "https://airport-data.com/full.jpg",
            "url_photo_thumbnail": "https://airport-data.com/thumb.jpg",
        },
        "flightroute": {
            "callsign": "DLH400",
            "callsign_icao": "DLH400",
            "callsign_iata": "LH400",
            "airline": {
                "name": "Lufthansa", "icao": "DLH", "iata": "LH",
                "country": "Germany", "country_iso": "DE", "callsign": "LUFTHANSA",
            },
            "origin": {
                "icao_code": "EDDF", "iata_code": "FRA", "name": "Frankfurt am Main Airport",
                "municipality": "Frankfurt am Main", "country_name": "Germany",
                "country_iso_name": "DE",
            },
            "destination": {
                "icao_code": "KJFK", "iata_code": "JFK", "name": "John F Kennedy International Airport",
                "municipality": "New York", "country_name": "United States",
                "country_iso_name": "US",
            },
        },
    }
}

_AIRCRAFT_ONLY_RESPONSE = {"response": {"aircraft": _FULL_RESPONSE["response"]["aircraft"]}}
_UNKNOWN_AIRCRAFT = {"response": "unknown aircraft"}
_UNKNOWN_CALLSIGN = {"response": "unknown callsign"}


class TestFullResponseParsing:
    def test_parses_aircraft_and_route(self):
        client = AdsbdbClient()
        with patch.object(client, "_session") as mock_session:
            mock_session.get.return_value = _resp(200, _FULL_RESPONSE)
            result = client.lookup("4b1805", "DLH400")

        assert result.aircraft.icao_type == "BCS3"
        assert result.aircraft.registered_owner == "Swiss International Air Lines"
        assert result.route.callsign_iata == "LH400"
        assert result.route.airline.name == "Lufthansa"
        assert result.route.origin.iata_code == "FRA"
        assert result.route.destination.iata_code == "JFK"
        client.close()


class TestPartialResponse:
    """Callsign unknown, aircraft known -> aircraft only, not an error."""

    def test_200_aircraft_only(self):
        client = AdsbdbClient()
        with patch.object(client, "_session") as mock_session:
            mock_session.get.return_value = _resp(200, _AIRCRAFT_ONLY_RESPONSE)
            result = client.lookup("4ca87c", "ZZZZZZ")

        assert result.aircraft is not None
        assert result.route is None
        client.close()

    def test_404_unknown_callsign_falls_back_to_aircraft_alone(self):
        """Empirically, some unmatched-but-well-formed callsigns 404 with
        'unknown callsign' rather than 200-aircraft-only. The aircraft
        must never be treated as unknown just because of that."""
        client = AdsbdbClient()
        call_log = []

        def fake_get(url, params=None, timeout=None):
            call_log.append(params)
            if params:  # first call, with callsign
                return _resp(404, _UNKNOWN_CALLSIGN)
            return _resp(200, _AIRCRAFT_ONLY_RESPONSE)  # fallback call, no callsign

        with patch.object(client, "_session") as mock_session:
            mock_session.get.side_effect = fake_get
            result = client.lookup("4ca87c", "SWR1")

        assert result.aircraft is not None
        assert result.route is None
        assert len(call_log) == 2  # combined attempt, then aircraft-only fallback
        client.close()


class TestUnknownHexNegativeCache:
    def test_second_lookup_uses_cache_no_request(self):
        client = AdsbdbClient()
        with patch.object(client, "_session") as mock_session:
            mock_session.get.return_value = _resp(404, _UNKNOWN_AIRCRAFT)
            r1 = client.lookup("ffffff")
            r2 = client.lookup("ffffff")

        assert r1.aircraft is None
        assert r2.aircraft is None
        assert mock_session.get.call_count == 1
        client.close()


class TestTtlExpiry:
    def test_refetches_after_ttl_expires(self):
        client = AdsbdbClient(aircraft_ttl_s=0.01)
        with patch.object(client, "_session") as mock_session:
            mock_session.get.return_value = _resp(200, _AIRCRAFT_ONLY_RESPONSE)
            client.lookup("4ca87c")
            time.sleep(0.02)
            client.lookup("4ca87c")

        assert mock_session.get.call_count == 2
        client.close()

    def test_no_refetch_before_ttl(self):
        client = AdsbdbClient(aircraft_ttl_s=300.0)
        with patch.object(client, "_session") as mock_session:
            mock_session.get.return_value = _resp(200, _AIRCRAFT_ONLY_RESPONSE)
            client.lookup("4ca87c")
            client.lookup("4ca87c")

        assert mock_session.get.call_count == 1
        client.close()


class TestNetworkFailure:
    def test_keeps_last_known_data_no_crash(self):
        client = AdsbdbClient(aircraft_ttl_s=0.01)
        with patch.object(client, "_session") as mock_session:
            mock_session.get.return_value = _resp(200, _AIRCRAFT_ONLY_RESPONSE)
            first = client.lookup("4ca87c")
            assert first.aircraft is not None

            time.sleep(0.02)  # let the cache go stale so a re-fetch is attempted
            mock_session.get.side_effect = requests.ConnectionError("offline")
            second = client.lookup("4ca87c")

        # Must not raise, and must still return the last-known-good data.
        assert second.aircraft is not None
        assert second.aircraft.icao_type == first.aircraft.icao_type
        client.close()

    def test_unknown_hex_and_no_prior_data_returns_empty_result(self):
        client = AdsbdbClient()
        with patch.object(client, "_session") as mock_session:
            mock_session.get.side_effect = requests.ConnectionError("offline")
            result = client.lookup("abcdef")

        assert result.aircraft is None
        assert result.route is None
        client.close()
