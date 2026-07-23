"""Tests for the Tomorrow.io weather client."""

import time
from unittest.mock import MagicMock, patch

import pytest

from flugradar.data_sources.weather import WeatherClient, WeatherData, _WEATHER_CODES


class TestWeatherData:
    def test_temperature_str(self):
        w = WeatherData(temperature_c=21.7)
        assert w.temperature_str == "22°C"

    def test_temperature_str_negative(self):
        w = WeatherData(temperature_c=-3.2)
        assert w.temperature_str == "-3°C"

    def test_wind_str(self):
        w = WeatherData(temperature_c=20, wind_speed_ms=5.14)
        assert "10kt" in w.wind_str

    def test_wind_str_none(self):
        w = WeatherData(temperature_c=20)
        assert w.wind_str == ""

    def test_condition_from_code(self):
        w = WeatherData(temperature_c=15, weather_code=1000, condition="Clear")
        assert w.condition == "Clear"


class TestWeatherClient:
    _SAMPLE_RESPONSE = {
        "data": {
            "time": "2025-01-15T12:00:00Z",
            "values": {
                "temperature": 18.5,
                "humidity": 65,
                "windSpeed": 3.2,
                "windDirection": 220,
                "weatherCode": 1101,
                "visibility": 10,
                "pressureSeaLevel": 1013.25,
                "cloudCover": 40,
            },
        }
    }

    def test_parse(self):
        client = WeatherClient("test-key", 47.0, 8.0)
        result = client._parse(self._SAMPLE_RESPONSE)
        assert result.temperature_c == 18.5
        assert result.humidity == 65
        assert result.wind_speed_ms == 3.2
        assert result.condition == "Partly Cloudy"
        assert result.pressure_hpa == 1013.25
        assert result.cloud_cover_pct == 40
        client.close()

    def test_parse_missing_values(self):
        client = WeatherClient("test-key", 47.0, 8.0)
        result = client._parse({"data": {"values": {"temperature": 5}}})
        assert result.temperature_c == 5
        assert result.humidity is None
        assert result.condition == ""
        client.close()

    @patch("flugradar.data_sources.weather.requests.Session")
    def test_fetch_and_cache(self, mock_session_cls):
        mock_resp = MagicMock()
        mock_resp.json.return_value = self._SAMPLE_RESPONSE
        mock_resp.raise_for_status = MagicMock()
        mock_session = MagicMock()
        mock_session.get.return_value = mock_resp
        mock_session_cls.return_value = mock_session

        client = WeatherClient("test-key", 47.0, 8.0, cache_ttl_s=300)

        result = client.get_weather()
        assert result is not None
        assert result.temperature_c == 18.5

        result2 = client.get_weather()
        assert result2 is result
        assert mock_session.get.call_count == 1

        client.close()

    @patch("flugradar.data_sources.weather.requests.Session")
    def test_fetch_failure_returns_cached(self, mock_session_cls):
        mock_resp = MagicMock()
        mock_resp.json.return_value = self._SAMPLE_RESPONSE
        mock_resp.raise_for_status = MagicMock()
        mock_session = MagicMock()
        mock_session.get.return_value = mock_resp
        mock_session_cls.return_value = mock_session

        client = WeatherClient("test-key", 47.0, 8.0, cache_ttl_s=0.01)
        first = client.get_weather()
        assert first is not None

        mock_session.get.side_effect = ConnectionError("offline")
        time.sleep(0.02)
        second = client.get_weather()
        assert second is first

        client.close()

    def test_no_data_returns_none(self):
        client = WeatherClient("test-key", 47.0, 8.0)
        assert client._cache is None
        assert client.get_weather() is None
        client.close()


class TestWeatherCodes:
    def test_known_codes(self):
        assert _WEATHER_CODES[1000] == "Clear"
        assert _WEATHER_CODES[8000] == "Thunderstorm"
        assert _WEATHER_CODES[5000] == "Snow"

    def test_all_codes_are_strings(self):
        for code, label in _WEATHER_CODES.items():
            assert isinstance(code, int)
            assert isinstance(label, str)
            assert len(label) > 0
