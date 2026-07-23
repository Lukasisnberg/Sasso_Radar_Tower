"""Tests for AirLabs flight enrichment client."""

import time
from unittest.mock import MagicMock, patch

import pytest

from flugradar.data_sources.enrichment import EnrichmentClient, FlightInfo
from flugradar.data_sources.models import Aircraft


class TestFlightInfo:
    def test_fields(self):
        info = FlightInfo(
            airline_name="Swiss",
            airline_iata="LX",
            flight_iata="LX1234",
            dep_iata="ZRH",
            arr_iata="LHR",
        )
        assert info.airline_name == "Swiss"
        assert info.dep_iata == "ZRH"


class TestEnrichmentClient:
    _SAMPLE_RESPONSE = {
        "response": [
            {
                "hex": "4b1234",
                "airline_name": "Swiss International Air Lines",
                "airline_iata": "LX",
                "flight_iata": "LX318",
                "dep_iata": "ZRH",
                "arr_iata": "LHR",
            }
        ]
    }

    def test_parse_response(self):
        client = EnrichmentClient("test-key")
        with patch.object(client, "_session") as mock_session:
            mock_resp = MagicMock()
            mock_resp.json.return_value = self._SAMPLE_RESPONSE
            mock_resp.raise_for_status = MagicMock()
            mock_session.get.return_value = mock_resp

            info = client._fetch("4b1234")
            assert info is not None
            assert info.airline_name == "Swiss International Air Lines"
            assert info.flight_iata == "LX318"
            assert info.dep_iata == "ZRH"
            assert info.arr_iata == "LHR"
        client.close()

    def test_parse_empty_response(self):
        client = EnrichmentClient("test-key")
        with patch.object(client, "_session") as mock_session:
            mock_resp = MagicMock()
            mock_resp.json.return_value = {"response": []}
            mock_resp.raise_for_status = MagicMock()
            mock_session.get.return_value = mock_resp

            info = client._fetch("000000")
            assert info is None
        client.close()

    def test_enrich_populates_fields(self):
        client = EnrichmentClient("test-key")
        ac = Aircraft(icao_hex="4b1234", lat=47.0, lon=8.0)

        info = FlightInfo(
            airline_name="Swiss",
            flight_iata="LX318",
            dep_iata="ZRH",
            arr_iata="LHR",
        )
        with patch.object(client, "_get_flight_info", return_value=info):
            client.enrich([ac])

        assert ac.airline == "Swiss"
        assert ac.flight_number == "LX318"
        assert ac.origin == "ZRH"
        assert ac.destination == "LHR"
        client.close()

    def test_enrich_skips_already_enriched(self):
        client = EnrichmentClient("test-key")
        ac = Aircraft(
            icao_hex="4b1234", lat=47.0, lon=8.0,
            airline="Existing", origin="AAA",
        )
        with patch.object(client, "_get_flight_info") as mock_fetch:
            client.enrich([ac])
            mock_fetch.assert_not_called()
        client.close()

    def test_enrich_does_not_overwrite_existing(self):
        client = EnrichmentClient("test-key")
        ac = Aircraft(icao_hex="4b1234", lat=47.0, lon=8.0, airline="MyAirline")

        info = FlightInfo(airline_name="Other", flight_iata="XX99", dep_iata="BBB", arr_iata="CCC")
        with patch.object(client, "_get_flight_info", return_value=info):
            client.enrich([ac])

        assert ac.airline == "MyAirline"
        assert ac.flight_number == "XX99"
        assert ac.origin == "BBB"
        client.close()

    def test_cache_prevents_repeated_fetch(self):
        client = EnrichmentClient("test-key", cache_ttl_s=300)
        info = FlightInfo(airline_name="Test")
        with patch.object(client, "_fetch", return_value=info) as mock_fetch:
            client._get_flight_info("aabbcc")
            client._get_flight_info("aabbcc")
            assert mock_fetch.call_count == 1
        client.close()

    def test_cache_expires(self):
        client = EnrichmentClient("test-key", cache_ttl_s=0.01)
        info = FlightInfo(airline_name="Test")
        with patch.object(client, "_fetch", return_value=info) as mock_fetch:
            client._get_flight_info("aabbcc")
            time.sleep(0.02)
            client._get_flight_info("aabbcc")
            assert mock_fetch.call_count == 2
        client.close()

    def test_fetch_failure_caches_none(self):
        client = EnrichmentClient("test-key", cache_ttl_s=300)
        with patch.object(client, "_fetch", side_effect=ConnectionError("offline")) as mock_fetch:
            result = client._get_flight_info("aabbcc")
            assert result is None
            result2 = client._get_flight_info("aabbcc")
            assert result2 is None
            assert mock_fetch.call_count == 1
        client.close()
