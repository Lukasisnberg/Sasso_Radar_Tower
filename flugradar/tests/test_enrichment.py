"""Tests for AirLabs flight enrichment client, and the adsbdb-backed
background enricher + FlightEnrichment source-priority coordinator."""

import time
from unittest.mock import MagicMock, patch

import pytest

from flugradar.data_sources.adsbdb import (
    AdsbdbAircraft,
    AdsbdbAirline,
    AdsbdbAirport,
    AdsbdbResult,
    AdsbdbRoute,
)
from flugradar.data_sources.enrichment import (
    AdsbdbEnricher,
    EnrichmentClient,
    FlightEnrichment,
    FlightInfo,
)
from flugradar.data_sources.models import Aircraft


def _wait_for(predicate, timeout=2.0, interval=0.02):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return predicate()


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


class TestAdsbdbEnricher:
    def test_background_lookup_populates_apply(self):
        mock_client = MagicMock()
        mock_client.lookup.return_value = AdsbdbResult(
            aircraft=AdsbdbAircraft(icao_type="BCS3", registered_owner="Swiss"),
            route=AdsbdbRoute(
                callsign_iata="LH400",
                airline=AdsbdbAirline(name="Lufthansa", icao="DLH"),
                origin=AdsbdbAirport(iata_code="FRA"),
                destination=AdsbdbAirport(iata_code="JFK"),
            ),
        )
        enricher = AdsbdbEnricher(mock_client)
        try:
            ac = Aircraft(icao_hex="4b1805", callsign="DLH400")
            enricher.enrich_priority(ac)
            assert _wait_for(lambda: enricher.get_cached("4b1805") is not None)

            enricher.apply([ac])
            assert ac.aircraft_type == "BCS3"
            assert ac.registered_owner == "Swiss"
            assert ac.airline == "Lufthansa"
            assert ac.airline_icao == "DLH"
            assert ac.flight_number == "LH400"
            assert ac.origin == "FRA"
            assert ac.destination == "JFK"
        finally:
            enricher.close()

    def test_apply_does_not_overwrite_existing_fields(self):
        mock_client = MagicMock()
        mock_client.lookup.return_value = AdsbdbResult(
            aircraft=AdsbdbAircraft(icao_type="BCS3"),
            route=AdsbdbRoute(airline=AdsbdbAirline(name="Other Airline")),
        )
        enricher = AdsbdbEnricher(mock_client)
        try:
            ac = Aircraft(icao_hex="4b1805", aircraft_type="A320", airline="Existing")
            enricher.enrich_priority(ac)
            assert _wait_for(lambda: enricher.get_cached("4b1805") is not None)

            enricher.apply([ac])
            assert ac.aircraft_type == "A320"
            assert ac.airline == "Existing"
        finally:
            enricher.close()

    def test_duplicate_requests_for_same_hex_lookup_once(self):
        mock_client = MagicMock()
        mock_client.lookup.return_value = AdsbdbResult(aircraft=AdsbdbAircraft(icao_type="A320"))
        enricher = AdsbdbEnricher(mock_client)
        try:
            ac = Aircraft(icao_hex="aabbcc")
            enricher.request(ac.icao_hex, priority=True)
            enricher.request(ac.icao_hex, priority=True)  # already pending, ignored
            assert _wait_for(lambda: enricher.get_cached("aabbcc") is not None)
            time.sleep(0.05)
            assert mock_client.lookup.call_count == 1
        finally:
            enricher.close()

    def test_enrich_nearest_sorts_by_distance_and_respects_limit(self):
        mock_client = MagicMock()
        mock_client.lookup.return_value = AdsbdbResult()
        enricher = AdsbdbEnricher(mock_client)
        try:
            aircraft = [
                Aircraft(icao_hex="c3", distance_km=30),
                Aircraft(icao_hex="c1", distance_km=10),
                Aircraft(icao_hex="c2", distance_km=20),
            ]
            enricher.enrich_nearest(aircraft, limit=2)
            assert _wait_for(lambda: mock_client.lookup.call_count >= 2)
            time.sleep(0.05)
            called_hexes = {c.args[0] for c in mock_client.lookup.call_args_list}
            assert called_hexes == {"c1", "c2"}
        finally:
            enricher.close()


class TestFlightEnrichmentPriority:
    def test_airlabs_wins_when_key_configured(self):
        airlabs = MagicMock()
        adsbdb = MagicMock()
        fe = FlightEnrichment(airlabs_client=airlabs, adsbdb_enricher=adsbdb)

        assert fe.using_adsbdb is False
        aircraft = [Aircraft(icao_hex="abc123")]
        fe.poll(aircraft, nearest_limit=5)

        airlabs.enrich.assert_called_once_with(aircraft)
        adsbdb.apply.assert_not_called()
        adsbdb.enrich_nearest.assert_not_called()

    def test_adsbdb_used_without_airlabs_key(self):
        adsbdb = MagicMock()
        fe = FlightEnrichment(adsbdb_enricher=adsbdb)

        assert fe.using_adsbdb is True
        aircraft = [Aircraft(icao_hex="abc123")]
        fe.poll(aircraft, nearest_limit=7)

        adsbdb.apply.assert_called_once_with(aircraft)
        adsbdb.enrich_nearest.assert_called_once_with(aircraft, 7)

    def test_neither_configured_is_a_no_op(self):
        fe = FlightEnrichment()
        assert fe.using_adsbdb is False
        fe.poll([Aircraft(icao_hex="abc123")])  # must not raise
        fe.close()  # must not raise

    def test_enrich_now_prefers_airlabs(self):
        airlabs = MagicMock()
        adsbdb = MagicMock()
        fe = FlightEnrichment(airlabs_client=airlabs, adsbdb_enricher=adsbdb)
        ac = Aircraft(icao_hex="abc123")

        fe.enrich_now(ac)

        airlabs.enrich.assert_called_once_with([ac])
        adsbdb.enrich_priority.assert_not_called()

    def test_enrich_now_uses_adsbdb_priority_path(self):
        adsbdb = MagicMock()
        fe = FlightEnrichment(adsbdb_enricher=adsbdb)
        ac = Aircraft(icao_hex="abc123")

        fe.enrich_now(ac)

        adsbdb.enrich_priority.assert_called_once_with(ac)
        adsbdb.apply.assert_called_once_with([ac])

    def test_get_adsbdb_photo_urls(self):
        adsbdb = MagicMock()
        adsbdb.get_cached.return_value = AdsbdbResult(
            aircraft=AdsbdbAircraft(
                url_photo="https://x/full.jpg", url_photo_thumbnail="https://x/thumb.jpg",
            )
        )
        fe = FlightEnrichment(adsbdb_enricher=adsbdb)

        thumb, full = fe.get_adsbdb_photo_urls("abc123")
        assert thumb == "https://x/thumb.jpg"
        assert full == "https://x/full.jpg"

    def test_get_adsbdb_photo_urls_none_when_uncached(self):
        adsbdb = MagicMock()
        adsbdb.get_cached.return_value = None
        fe = FlightEnrichment(adsbdb_enricher=adsbdb)
        assert fe.get_adsbdb_photo_urls("abc123") is None
